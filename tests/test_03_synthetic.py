"""Phase 3: synthetic task — generate, splits, score, seed rules."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from sklearn.metrics import roc_auc_score

from harness.protocol import load
from harness.tasks.synthetic import SyntheticTask, generate
from helpers import placeholder_protocol, run_candidate

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "candidate" / "rules.jsonl"
PROTOCOL = ROOT / "protocols" / "synthetic.yaml"


def test_deterministic():
    a = generate(1, n_impressions=5_000)
    b = generate(1, n_impressions=5_000)
    c = generate(2, n_impressions=5_000)
    assert a.equals(b)
    assert not a.equals(c)


def test_funnel_rates():
    t = generate(0, n_impressions=1_000_000)
    click = np.asarray(t.column("click"))
    conv = np.asarray(t.column("conversion"))
    click_rate = click.mean()
    assert 0.02 <= click_rate <= 0.04
    clicked = click == 1
    cvr = conv[clicked].mean()
    assert 0.08 <= cvr <= 0.12
    assert int(conv[clicked].sum()) >= 2_000


def _single_feature_auc(table: pa.Table, feature: str) -> float:
    click = np.asarray(table.column("click"))
    conv = np.asarray(table.column("conversion"))
    feat = np.asarray(table.column(feature), dtype=np.float64)
    mask = click == 1
    return float(roc_auc_score(conv[mask], feat[mask]))


def test_leak_feature_auc():
    t = generate(0, n_impressions=200_000)
    assert _single_feature_auc(t, "f_leak") > 0.9


def test_zero_feature_auc():
    t = generate(0, n_impressions=1_000_000)
    auc = _single_feature_auc(t, "f_zero")
    assert 0.48 <= auc <= 0.52


def test_true_feature_auc():
    t = generate(0, n_impressions=1_000_000)
    auc = _single_feature_auc(t, "f_true")
    assert 0.60 <= auc <= 0.72


def test_marginal_feature_auc():
    t = generate(0, n_impressions=1_000_000)
    auc = _single_feature_auc(t, "f_marginal")
    assert 0.53 <= auc <= 0.60


def test_splits_by_rule(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=10_000)
    paths = task.prepare(proto, tmp_path / "data")
    full = pq.read_table(tmp_path / "data" / "harness_only" / "generated.parquet")
    train = pq.read_table(paths.train)
    search = pq.read_table(paths.search_validation)
    holdout = pq.read_table(paths.holdout_validation)
    n = full.num_rows
    n_search = n // 10
    n_holdout = n // 10
    assert search.num_rows == n_search
    assert holdout.num_rows == n_holdout
    assert train.num_rows == n - n_search - n_holdout
    assert paths.holdout_validation.is_relative_to(tmp_path / "data" / "harness_only")
    assert (tmp_path / "data" / "harness_only" / "digests.json").is_file()
    assert not (tmp_path / "data" / "generated.parquet").exists()
    search_ids = set(search.column("sample_id").to_pylist())
    holdout_ids = set(holdout.column("sample_id").to_pylist())
    train_ids = set(train.column("sample_id").to_pylist())
    assert search_ids.isdisjoint(holdout_ids)
    assert search_ids.isdisjoint(train_ids)
    assert holdout_ids.isdisjoint(train_ids)
    assert search_ids | holdout_ids | train_ids == set(full.column("sample_id").to_pylist())
    all_ids = full.column("sample_id").to_pylist()
    assert search.column("sample_id").to_pylist() == all_ids[-n_search:]
    assert holdout.column("sample_id").to_pylist() == all_ids[-n_search - n_holdout : -n_search]


def test_candidate_env_has_no_holdout(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=5_000)
    paths = task.prepare(proto, tmp_path / "data")
    env = task.candidate_env(paths)
    assert set(env.keys()) == {"TRAIN", "VALID"}
    for v in env.values():
        assert "holdout" not in v.lower()
        assert "harness_only" not in v.lower()


def test_score_populations(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=5_000)
    paths = task.prepare(proto, tmp_path / "data")
    valid = pq.read_table(paths.search_validation)
    click = np.asarray(valid.column("click"))
    conv = np.asarray(valid.column("conversion"))
    p_cvr = np.where(click == 1, conv.astype(np.float64) * 0.9 + 0.05, 0.99).astype(
        np.float32
    )
    p_click = (click.astype(np.float32) * 0.8 + 0.1).astype(np.float32)
    preds_path = tmp_path / "preds.parquet"
    pq.write_table(
        pa.table(
            {
                "sample_id": valid.column("sample_id"),
                "p_click": p_click,
                "p_conversion_given_click": p_cvr,
            }
        ),
        preds_path,
        compression="zstd",
    )
    metrics = task.score(preds_path, "search")
    mask = click == 1
    clicked_auc = float(roc_auc_score(conv[mask], p_cvr[mask]))
    all_rows_auc = float(roc_auc_score(conv, p_cvr))
    assert metrics["cvr_auc"] == pytest.approx(clicked_auc, abs=1e-9)
    assert all_rows_auc != clicked_auc


def test_score_rejects_duplicate_ids(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=1_000)
    paths = task.prepare(proto, tmp_path / "data")
    valid = pq.read_table(paths.search_validation)
    n = valid.num_rows
    ids = np.asarray(valid.column("sample_id"), dtype=np.int64).copy()
    ids[1] = ids[0]
    preds_path = tmp_path / "dup.parquet"
    pq.write_table(
        pa.table(
            {
                "sample_id": ids,
                "p_click": np.linspace(0.1, 0.9, n).astype(np.float32),
                "p_conversion_given_click": np.linspace(0.1, 0.9, n).astype(np.float32),
            }
        ),
        preds_path,
        compression="zstd",
    )
    with pytest.raises(ValueError, match="duplicate sample_id"):
        task.score(preds_path, "search")


def test_score_hand_computed(tmp_path: Path):
    """10-row fixture; AUC by hand including a tie — library-independent guard."""
    y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1], dtype=np.float64)
    s = np.array([0.1, 0.2, 0.3, 0.5, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], dtype=np.float64)
    hand = 24.5 / 25.0
    assert roc_auc_score(y, s) == pytest.approx(hand, abs=1e-12)

    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=100)
    paths = task.prepare(proto, tmp_path / "data")
    click = np.array([1, 1, 1, 1, 1, 1, 1, 1, 0, 0], dtype=np.int8)
    labels = pa.table(
        {
            "sample_id": np.arange(10, dtype=np.int64),
            "click": click,
            "conversion": y.astype(np.int8),
        }
    )
    hand_cvr = 14.5 / 15.0
    pq.write_table(labels, paths.search_validation, compression="zstd", store_schema=False)
    # Drop cached tables so score() reads the rewritten search parquet from disk.
    task._tables.clear()
    assert task.rows("search") == 10
    preds = pa.table(
        {
            "sample_id": np.arange(10, dtype=np.int64),
            "p_click": np.linspace(0.1, 0.9, 10).astype(np.float32),
            "p_conversion_given_click": s.astype(np.float32),
        }
    )
    preds_path = tmp_path / "p.parquet"
    pq.write_table(preds, preds_path, compression="zstd")
    metrics = task.score(preds_path, "search")
    assert metrics["cvr_auc"] == pytest.approx(hand_cvr, abs=1e-6)


def test_seed_rules_parse():
    lines = [ln for ln in RULES.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 7
    ids = []
    required = {"id", "statement", "check", "pattern", "severity", "source", "mode"}
    for ln in lines:
        obj = json.loads(ln)
        assert required <= set(obj.keys())
        assert obj["check"] in {"static", "llm"}
        assert obj["severity"] in {"fail", "warn"}
        assert obj["mode"] in {"forbid", "require"}
        assert obj["source"] == "seed"
        assert obj["pattern"] is None or isinstance(obj["pattern"], str)
        ids.append(obj["id"])
    assert ids == [f"C{i}" for i in range(1, 8)]
    c1 = json.loads(lines[0])
    assert c1["id"] == "C1" and c1["mode"] == "forbid"


@pytest.mark.slow
def test_prepare_verifies_filled_hashes(tmp_path: Path):
    proto = load(PROTOCOL)
    task = SyntheticTask(n_impressions=1_000_000)
    task.prepare(proto, tmp_path / "ok")
    bad = copy.deepcopy(yaml.safe_load(PROTOCOL.read_text()))
    bad["ruler"]["data"]["train"]["sha256"] = "f" * 64
    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        SyntheticTask(n_impressions=1_000_000).prepare(load(bad_path), tmp_path / "bad")


def test_unseen_id_in_valid(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=5_000)
    paths = task.prepare(proto, tmp_path / "data")
    valid = pq.read_table(paths.search_validation)
    train = pq.read_table(paths.train)
    train_items = set(train.column("item_id").to_pylist())
    unseen = max(train_items) + 10_000
    assert unseen not in train_items
    cols = {name: valid.column(name) for name in valid.column_names}
    item = np.asarray(valid.column("item_id")).copy()
    item[0] = unseen
    cols["item_id"] = pa.array(item, type=pa.int32())
    pq.write_table(pa.table(cols), paths.search_validation, compression="zstd")

    ws = tmp_path / "ws"
    proc = run_candidate(paths, ws)
    assert proc.returncode == 0, proc.stderr
    assert (ws / "result.json").exists()
