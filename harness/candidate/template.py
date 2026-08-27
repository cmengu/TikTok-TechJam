"""Phase 3: baseline training script the agent edits (run as python -m harness.candidate.template)."""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
import torch.nn as nn

from harness.candidate import report

BASE_FEATURES = ("user_id", "item_id", "cat_a", "cat_b", "cat_c")
FAILURE_ENV = "SYNTHETIC_FAIL"
OOV = 0


def _parse_features(raw: str | None) -> list[str]:
    if not raw or raw.strip() == "base":
        return list(BASE_FEATURES)
    parts: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "base":
            parts.extend(BASE_FEATURES)
        else:
            parts.append(tok)
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _inject_failure(mode: str, when: str) -> None:
    if mode != when:
        return
    if mode == "crash":
        raise RuntimeError("SYNTHETIC_FAIL=crash")
    if mode == "oom_cuda":
        raise RuntimeError("CUDA out of memory")
    if mode == "oom_host":
        os.kill(os.getpid(), 9)
    if mode == "hang":
        report.progress(0, 1, 0.0)
        while True:
            time.sleep(60)
    if mode == "nan":
        return  # handled at first progress
    if mode == "no_result":
        return
    if mode == "bad_schema":
        return


class _Model(nn.Module):
    def __init__(self, n_emb: dict[str, int], emb_dim: int = 8, dropout: float = 0.0):
        super().__init__()
        self.embs = nn.ModuleDict(
            {
                name: nn.Embedding(n + 1, emb_dim, padding_idx=OOV)  # +1 for OOV@0
                for name, n in n_emb.items()
            }
        )
        self.dropout = nn.Dropout(dropout)
        in_dim = emb_dim * len(n_emb)
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
        )
        self.head_click = nn.Linear(16, 1)
        self.head_cvr = nn.Linear(16, 1)

    def forward(self, batch: dict[str, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        parts = [self.embs[k](batch[k]) for k in self.embs]
        x = self.dropout(torch.cat(parts, dim=-1))
        h = self.mlp(x)
        return self.head_click(h).squeeze(-1), self.head_cvr(h).squeeze(-1)


def _build_vocab(train_cols: dict[str, np.ndarray], features: list[str]) -> dict[str, dict[int, int]]:
    vocabs: dict[str, dict[int, int]] = {}
    for name in features:
        if name.startswith("f_"):
            continue  # continuous planted features — no vocab
        vals = train_cols[name]
        uniq = np.unique(vals)
        # reserve 0 for OOV
        vocabs[name] = {int(v): i + 1 for i, v in enumerate(uniq.tolist())}
    return vocabs


def _encode(cols: dict[str, np.ndarray], features: list[str], vocabs: dict[str, dict[int, int]], idx: np.ndarray) -> dict[str, torch.Tensor]:
    batch: dict[str, torch.Tensor] = {}
    for name in features:
        if name.startswith("f_"):
            # bucket continuous features into a small embedding via digitization
            raw = cols[name][idx].astype(np.float64)
            # map to 1..16 via ranks within batch is wrong; use fixed bins from sign/magnitude
            buckets = np.clip((raw * 2).astype(np.int64) + 8, 1, 16)
            batch[name] = torch.tensor(buckets, dtype=torch.long)
        else:
            vocab = vocabs[name]
            mapped = np.fromiter(
                (vocab.get(int(v), OOV) for v in cols[name][idx]),
                dtype=np.int64,
                count=len(idx),
            )
            batch[name] = torch.from_numpy(mapped)
    return batch


def main() -> None:
    fail = os.environ.get(FAILURE_ENV, "").strip()
    device_s = os.environ.get("DEVICE", "cpu")
    seed = int(os.environ.get("SEED", "0"))
    train_path = Path(os.environ["TRAIN"])
    valid_path = Path(os.environ["VALID"])
    workspace = Path(os.environ.get("WORKSPACE", "."))
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ["WORKSPACE"] = str(workspace)

    features = _parse_features(os.environ.get("FEATURES"))
    batch_size = int(os.environ.get("BATCH", "4096"))
    lr = float(os.environ.get("LR", "1e-3"))
    epochs = int(os.environ.get("EPOCHS", "1"))

    _inject_failure(fail, "crash")
    _inject_failure(fail, "oom_cuda")
    _inject_failure(fail, "oom_host")
    _inject_failure(fail, "hang")

    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device(device_s)

    train_tbl = pq.read_table(train_path)
    valid_tbl = pq.read_table(valid_path)
    train_cols = {c: np.asarray(train_tbl.column(c)) for c in train_tbl.column_names}
    valid_cols = {c: np.asarray(valid_tbl.column(c)) for c in valid_tbl.column_names}

    # Continuous planted features need an embedding slot too.
    emb_features = list(features)
    vocabs = _build_vocab(train_cols, [f for f in emb_features if not f.startswith("f_")])
    n_emb: dict[str, int] = {f: len(vocabs[f]) for f in vocabs}
    for f in emb_features:
        if f.startswith("f_"):
            n_emb[f] = 16

    model = _Model(n_emb, emb_dim=8, dropout=0.0).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss()

    n = len(train_cols["sample_id"])
    n_steps = max(1, (n + batch_size - 1) // batch_size * epochs)
    step = 0
    rng = np.random.default_rng(seed)

    model.train()
    for _epoch in range(epochs):
        order = rng.permutation(n)
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            batch = _encode(train_cols, emb_features, vocabs, idx)
            batch = {k: v.to(device) for k, v in batch.items()}
            y_click = torch.tensor(
                train_cols["click"][idx].astype(np.float32), device=device
            )
            y_cvr = torch.tensor(
                train_cols["conversion"][idx].astype(np.float32), device=device
            )
            # Only clicked rows contribute to CVR loss.
            click_mask = y_click > 0.5

            logit_c, logit_v = model(batch)
            loss = bce(logit_c, y_click)
            if click_mask.any():
                loss = loss + bce(logit_v[click_mask], y_cvr[click_mask])

            opt.zero_grad()
            loss.backward()
            opt.step()

            step += 1
            loss_v = float(loss.detach().cpu())
            if fail == "nan" and step == 1:
                loss_v = float("nan")
            report.progress(step, n_steps, loss_v)
            report.checkpoint.save(
                {"step": step, "state_dict": model.state_dict()}
            )

    if fail == "no_result":
        sys.exit(0)
    if fail == "bad_schema":
        report.result({"ctr_auc": 0.5}, preds_path=workspace / "preds.parquet")
        sys.exit(0)

    # Predict on VALID.
    model.eval()
    v_n = len(valid_cols["sample_id"])
    p_click = np.zeros(v_n, dtype=np.float32)
    p_cvr = np.zeros(v_n, dtype=np.float32)
    with torch.no_grad():
        for start in range(0, v_n, batch_size):
            idx = np.arange(start, min(start + batch_size, v_n))
            batch = _encode(valid_cols, emb_features, vocabs, idx)
            batch = {k: v.to(device) for k, v in batch.items()}
            logit_c, logit_v = model(batch)
            p_click[idx] = torch.sigmoid(logit_c).cpu().numpy()
            p_cvr[idx] = torch.sigmoid(logit_v).cpu().numpy()

    import pyarrow as pa

    preds_path = workspace / "preds.parquet"
    preds = pa.table(
        {
            "sample_id": np.asarray(valid_cols["sample_id"], dtype=np.int64),
            "p_click": p_click,
            "p_conversion_given_click": p_cvr,
        }
    )
    pq.write_table(preds, preds_path, compression="zstd")

    # Local AUCs for the printed summary (harness score() is authoritative).
    from sklearn.metrics import roc_auc_score

    y_c = np.asarray(valid_cols["click"], dtype=np.float64)
    ctr = float(roc_auc_score(y_c, p_click))
    clicked = y_c > 0.5
    cvr = float(
        roc_auc_score(
            np.asarray(valid_cols["conversion"], dtype=np.float64)[clicked],
            p_cvr[clicked],
        )
    )
    report.result({"ctr_auc": ctr, "cvr_auc": cvr}, preds_path=preds_path)
    print(f"ctr_auc={ctr:.6f} cvr_auc={cvr:.6f}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
