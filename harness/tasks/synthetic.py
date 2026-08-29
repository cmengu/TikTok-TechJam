"""Phase 3: synthetic funnel benchmark with planted effects."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Literal

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score

from harness.protocol import Protocol
from harness.tasks.base import TaskPaths

FAILURE_ENV = "SYNTHETIC_FAIL"
PLACEHOLDER_MAX = 15  # yaml used 000…0001 .. 000…0005


def _is_placeholder(value: str) -> bool:
    try:
        return int(str(value), 16) <= PLACEHOLDER_MAX
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_parquet(table: pa.Table, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # store_schema=False keeps digests stable across Arrow builds.
    pq.write_table(
        table,
        path,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
        store_schema=False,
    )
    return _sha256_file(path)


def generate(
    seed: int,
    n_users: int = 20_000,
    n_items: int = 2_000,
    n_impressions: int = 1_000_000,
) -> pa.Table:
    rng = np.random.default_rng(int(seed))
    user_lat = rng.normal(0.0, 1.0, size=n_users)
    item_lat = rng.normal(0.0, 1.0, size=n_items)
    user_cvr = rng.normal(0.0, 1.0, size=n_users)
    item_cvr = rng.normal(0.0, 1.0, size=n_items)

    user_id = rng.integers(0, n_users, size=n_impressions, dtype=np.int32)
    item_id = rng.integers(0, n_items, size=n_impressions, dtype=np.int32)
    cat_a = rng.integers(0, 16, size=n_impressions, dtype=np.int32)
    cat_b = rng.integers(0, 32, size=n_impressions, dtype=np.int32)
    cat_c = rng.integers(0, 8, size=n_impressions, dtype=np.int32)

    click_score = (
        user_lat[user_id]
        + item_lat[item_id]
        + 0.05 * cat_a.astype(np.float64)
        + rng.normal(0.0, 0.4, size=n_impressions)
    )
    # Exact-rate clicks (~3%): threshold on score, then Bernoulli noise is skipped
    # so funnel tests stay stable across seeds.
    n_click = max(1, int(round(0.03 * n_impressions)))
    click_cut = float(np.partition(click_score, -n_click)[-n_click])
    click = (click_score >= click_cut).astype(np.int8)
    # Break exact ties so we land on n_click.
    extra = int(click.sum()) - n_click
    if extra > 0:
        tied = np.flatnonzero(click_score == click_cut)
        rng.shuffle(tied)
        click[tied[:extra]] = 0

    cvr_latent = (
        0.8 * user_cvr[user_id]
        + 0.8 * item_cvr[item_id]
        + rng.normal(0.0, 0.35, size=n_impressions)
    )
    clicked_idx = np.flatnonzero(click == 1)
    conversion = np.zeros(n_impressions, dtype=np.int8)
    if len(clicked_idx):
        n_conv = max(1, int(round(0.10 * len(clicked_idx))))
        cvr_scores = cvr_latent[clicked_idx]
        cvr_cut = float(np.partition(cvr_scores, -n_conv)[-n_conv])
        take = cvr_scores >= cvr_cut
        chosen = clicked_idx[take]
        extra_c = int(take.sum()) - n_conv
        if extra_c > 0:
            tied = chosen[cvr_scores[take] == cvr_cut]
            rng.shuffle(tied)
            drop = set(tied[:extra_c].tolist())
            chosen = np.array([i for i in chosen if i not in drop], dtype=np.int64)
        conversion[chosen] = 1

    # Four planted effects (scored on clicked rows for conversion).
    # Tuned so: 1M single-feature AUC stays in phase-3 bands; 200K/8ep model Δ
    # clears PROMOTE_FLOOR with all-positive seeds but stays under
    # LEAK_TRIGGER_BANDS × sd_delta_full (else f_true is mislabeled leaked).
    f_true = (0.24 * cvr_latent + rng.normal(0.0, 1.25, size=n_impressions)).astype(
        np.float32
    )
    f_marginal = (
        0.14 * cvr_latent + rng.normal(0.0, 1.42, size=n_impressions)
    ).astype(np.float32)
    f_zero = rng.normal(0.0, 1.0, size=n_impressions).astype(np.float32)
    f_leak = (
        conversion.astype(np.float32) + rng.normal(0.0, 0.05, size=n_impressions)
    ).astype(np.float32)

    # Short user history lists (excluded from base FEATURES in v1).
    k = rng.integers(0, 5, size=n_impressions, dtype=np.int32)
    offsets = np.concatenate([[0], np.cumsum(k, dtype=np.int64)]).astype(np.int32)
    total = int(offsets[-1])
    hist_ids = rng.integers(0, n_items, size=total, dtype=np.int32)
    hist_w = rng.random(total).astype(np.float32)
    hist_values = pa.StructArray.from_arrays(
        [hist_ids, hist_w], names=["id", "weight"]
    )
    hist = pa.ListArray.from_arrays(offsets, hist_values)

    sample_id = np.arange(n_impressions, dtype=np.int64)

    return pa.table(
        {
            "sample_id": sample_id,
            "user_id": user_id,
            "item_id": item_id,
            "cat_a": cat_a,
            "cat_b": cat_b,
            "cat_c": cat_c,
            "hist": hist,
            "click": click,
            "conversion": conversion,
            "f_true": f_true,
            "f_marginal": f_marginal,
            "f_zero": f_zero,
            "f_leak": f_leak,
        }
    )


def _split_tables(table: pa.Table) -> tuple[pa.Table, pa.Table, pa.Table]:
    n = table.num_rows
    n_search = n // 10
    n_holdout = n // 10
    # last 10% = search_validation; preceding 10% = holdout; rest = train
    search = table.slice(n - n_search, n_search)
    holdout = table.slice(n - n_search - n_holdout, n_holdout)
    train = table.slice(0, n - n_search - n_holdout)
    return train, search, holdout


def _score_script_sha() -> str:
    return hashlib.sha256(
        inspect.getsource(SyntheticTask.score).encode("utf-8")
    ).hexdigest()


class SyntheticTask:
    name = "synthetic"

    def __init__(self, n_impressions: int = 1_000_000) -> None:
        self.n_impressions = int(n_impressions)
        self._paths: TaskPaths | None = None
        self._tables: dict[str, pa.Table] = {}

    def prepare(self, protocol: Protocol, root: Path, *, seed: int = 0) -> TaskPaths:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        harness_only = root / "harness_only"
        harness_only.mkdir(parents=True, exist_ok=True)

        full = generate(seed=seed, n_impressions=self.n_impressions)
        train, search, holdout = _split_tables(full)

        # Candidate-visible: train + search only.
        train_path = root / "train.parquet"
        search_path = root / "search_validation.parquet"
        # Harness-only: holdout, full dump, digests — never in candidate_env.
        holdout_path = harness_only / "holdout_validation.parquet"
        full_path = harness_only / "generated.parquet"

        digests = {
            "train": _write_parquet(train, train_path),
            "search": _write_parquet(search, search_path),
            "holdout": _write_parquet(holdout, holdout_path),
            "test": _write_parquet(full, full_path),
        }
        script_sha = _score_script_sha()

        ruler = protocol.ruler
        expected = {
            "train": ruler["data"]["train"]["sha256"],
            "test": ruler["data"]["test"]["sha256"],
            "search": ruler["splits"]["search_validation"]["sha256"],
            "holdout": ruler["splits"]["holdout_validation"]["sha256"],
            "script": ruler["scoring"]["script_sha"],
        }
        actual = {
            "train": digests["train"],
            "test": digests["test"],
            "search": digests["search"],
            "holdout": digests["holdout"],
            "script": script_sha,
        }
        for key, exp in expected.items():
            if _is_placeholder(str(exp)):
                continue
            if str(exp) != actual[key]:
                raise ValueError(
                    f"sha256 mismatch for {key}: yaml={exp} disk={actual[key]}"
                )

        self._paths = TaskPaths(
            train=train_path,
            search_validation=search_path,
            holdout_validation=holdout_path,
            scoring_script=Path(__file__),
        )
        self._tables = {
            "train": train,
            "search": search,
            "holdout": holdout,
        }
        (harness_only / "digests.json").write_text(
            json.dumps({**digests, "script": script_sha}, indent=2) + "\n",
            encoding="utf-8",
        )
        return self._paths

    def candidate_env(self, paths: TaskPaths) -> dict:
        return {
            "TRAIN": str(paths.train),
            "VALID": str(paths.search_validation),
        }

    def score(
        self, preds_path: Path, split: Literal["search", "holdout"]
    ) -> dict[str, float]:
        if self._paths is None and split not in self._tables:
            raise RuntimeError("prepare() must be called before score()")
        labels = self._tables.get(split)
        if labels is None:
            path = (
                self._paths.search_validation
                if split == "search"
                else self._paths.holdout_validation  # type: ignore[union-attr]
            )
            labels = pq.read_table(path)

        preds = pq.read_table(preds_path)
        required = {"sample_id", "p_click", "p_conversion_given_click"}
        missing = required - set(preds.column_names)
        if missing:
            raise ValueError(f"preds missing columns: {sorted(missing)}")

        lab_ids_arr = np.asarray(labels.column("sample_id"), dtype=np.int64)
        pred_ids_arr = np.asarray(preds.column("sample_id"), dtype=np.int64)
        if len(pred_ids_arr) != len(set(pred_ids_arr.tolist())):
            raise ValueError("duplicate sample_id values in preds")
        lab_ids = set(lab_ids_arr.tolist())
        pred_ids = set(pred_ids_arr.tolist())
        if lab_ids != pred_ids:
            raise ValueError(
                f"sample_id sets differ: labels={len(lab_ids)} preds={len(pred_ids)} "
                f"only_labels={len(lab_ids - pred_ids)} only_preds={len(pred_ids - lab_ids)}"
            )
        # Align preds to label row order via sample_id (never assume row order).
        pred_pos = {int(i): k for k, i in enumerate(pred_ids_arr.tolist())}
        idx = np.fromiter(
            (pred_pos[int(i)] for i in lab_ids_arr.tolist()), dtype=np.int64
        )

        y_click = np.asarray(labels.column("click"), dtype=np.float64)
        y_conv = np.asarray(labels.column("conversion"), dtype=np.float64)
        p_click = np.asarray(preds.column("p_click"), dtype=np.float64)[idx]
        p_cvr = np.asarray(
            preds.column("p_conversion_given_click"), dtype=np.float64
        )[idx]
        ctr_auc = float(roc_auc_score(y_click, p_click))
        clicked = y_click > 0.5
        if not np.any(clicked):
            raise ValueError("no clicked rows to score cvr_auc")
        cvr_auc = float(roc_auc_score(y_conv[clicked], p_cvr[clicked]))
        return {"ctr_auc": ctr_auc, "cvr_auc": cvr_auc}

    def rows(self, split: str) -> int:
        if split == "test":
            return self.n_impressions
        if split in self._tables:
            return self._tables[split].num_rows
        if self._paths is None:
            raise RuntimeError("prepare() must be called before rows()")
        mapping = {
            "train": self._paths.train,
            "search": self._paths.search_validation,
            "holdout": self._paths.holdout_validation,
        }
        if split not in mapping:
            raise KeyError(split)
        return pq.read_table(mapping[split], columns=["sample_id"]).num_rows
