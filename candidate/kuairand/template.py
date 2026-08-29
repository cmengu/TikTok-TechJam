"""KuaiRand FM baseline candidate — numpy + csv only, no valid-label early stop."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import numpy as np

import report

FIELDS = ("user_id", "video_id", "author_id", "tab", "dur_bucket")
DEFAULT_EPOCHS = 11


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _read_rows(path: Path, *, with_label: bool) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _bucket_edges(durations: list[float], n: int = 10) -> np.ndarray:
    return np.quantile(np.asarray(durations, dtype=np.float64), np.linspace(0, 1, n + 1)[1:-1])


def _encode_rows(
    rows: list[dict[str, str]],
    vocabs: list[dict[str, int]],
    unk: list[int],
    offsets: np.ndarray,
    edges: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    x = np.empty((len(rows), len(FIELDS)), dtype=np.int32)
    y = None
    if rows and "long_view" in rows[0]:
        y = np.empty(len(rows), dtype=np.float32)
    for n, row in enumerate(rows):
        raw = [
            row["user_id"],
            row["video_id"],
            row["author_id"],
            row["tab"],
            str(int(np.searchsorted(edges, float(row["duration_ms"])))),
        ]
        for i, v in enumerate(raw):
            x[n, i] = vocabs[i].get(v, unk[i]) + offsets[i]
        if y is not None:
            y[n] = float(row["long_view"])
    return x, y


def _build_vocabs(train_rows: list[dict[str, str]], edges: np.ndarray):
    vocabs = [dict() for _ in FIELDS]
    for row in train_rows:
        raw = [
            row["user_id"],
            row["video_id"],
            row["author_id"],
            row["tab"],
            str(int(np.searchsorted(edges, float(row["duration_ms"])))),
        ]
        for i, v in enumerate(raw):
            if v not in vocabs[i]:
                vocabs[i][v] = len(vocabs[i])
    unk = [len(v) for v in vocabs]
    field_dims = [len(v) + 1 for v in vocabs]
    offsets = np.cumsum([0] + field_dims[:-1]).astype(np.int32)
    return vocabs, unk, offsets


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


class FM:
    def __init__(self, dim: int, k: int = 16, lr: float = 0.001, l2: float = 1e-6, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.V = rng.normal(0, 0.01, (dim, k)).astype(np.float32)
        self.W = np.zeros(dim, dtype=np.float32)
        self.b = np.float32(0.0)
        self.lr, self.l2 = lr, l2
        self.mV = np.zeros_like(self.V)
        self.vV = np.zeros_like(self.V)
        self.mW = np.zeros_like(self.W)
        self.vW = np.zeros_like(self.W)
        self.t = 0

    def logits(self, X: np.ndarray):
        e = self.V[X]
        s = e.sum(1)
        inter = 0.5 * ((s**2).sum(1) - (e**2).sum((1, 2)))
        return self.b + self.W[X].sum(1) + inter, e, s

    def step(self, X: np.ndarray, y: np.ndarray) -> float:
        bsz = len(y)
        z, e, s = self.logits(X)
        g = ((sigmoid(z) - y) / bsz).astype(np.float32)
        gV = np.zeros_like(self.V)
        gW = np.zeros_like(self.W)
        np.add.at(gW, X, g[:, None])
        np.add.at(gV, X, g[:, None, None] * (s[:, None, :] - e))
        gV += self.l2 * self.V
        gW += self.l2 * self.W
        self.t += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        for P, G, M, Vv in ((self.V, gV, self.mV, self.vV), (self.W, gW, self.mW, self.vW)):
            M *= b1
            M += (1 - b1) * G
            Vv *= b2
            Vv += (1 - b2) * (G * G)
            P -= self.lr * (M / (1 - b1**self.t)) / (np.sqrt(Vv / (1 - b2**self.t)) + eps)
        self.b -= self.lr * g.sum()
        return float(
            -np.mean(y * np.log(sigmoid(z) + 1e-9) + (1 - y) * np.log(1 - sigmoid(z) + 1e-9))
        )

    def predict(self, X: np.ndarray, bs: int = 200_000) -> np.ndarray:
        return np.concatenate([self.logits(X[i : i + bs])[0] for i in range(0, len(X), bs)])


def _write_preds(path: Path, rows: list[dict[str, str]], scores: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_id", "user_id", "video_id", "score"])
        for i, (row, score) in enumerate(zip(rows, scores)):
            writer.writerow([i, row["user_id"], row["video_id"], f"{float(score):.6g}"])


def main() -> None:
    train_path = Path(os.environ["TRAIN"])
    valid_path = Path(os.environ.get("ORACLE") or os.environ["VALID"])
    seed = _env_int("SEED", 0)
    epochs = _env_int("EPOCHS", DEFAULT_EPOCHS)
    batch = _env_int("BATCH", 8192)
    lr = float(os.environ.get("LR", "0.001"))
    workspace = Path(os.environ["WORKSPACE"])

    train_rows = _read_rows(train_path, with_label=True)
    valid_rows = _read_rows(valid_path, with_label=False)
    edges = _bucket_edges([float(r["duration_ms"]) for r in train_rows])
    vocabs, unk, offsets = _build_vocabs(train_rows, edges)
    dim = int(offsets[-1] + len(vocabs[-1]) + 1)

    xtr, ytr = _encode_rows(train_rows, vocabs, unk, offsets, edges)
    xva, _ = _encode_rows(valid_rows, vocabs, unk, offsets, edges)

    model = FM(dim, k=16, lr=lr, seed=seed)
    rng = np.random.default_rng(seed)
    for ep in range(1, epochs + 1):
        idx = rng.permutation(len(ytr))
        losses = []
        for i in range(0, len(idx), batch):
            losses.append(model.step(xtr[idx[i : i + batch]], ytr[idx[i : i + batch]]))
        report.progress(ep, epochs, float(np.mean(losses)))
        report.checkpoint.save(ep, f"epoch-{ep}".encode())

    preds_path = workspace / "preds.csv"
    _write_preds(preds_path, valid_rows, model.predict(xva))
    report.result({"primary": 0.0}, preds_path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
