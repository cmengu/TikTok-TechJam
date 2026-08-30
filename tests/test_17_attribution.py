"""Step 10: attribution is a function of declared observables, not a constant."""

from __future__ import annotations

import json
from pathlib import Path

from helpers import placeholder_protocol
from harness.attribute import (
    Claim,
    Observable,
    attribute,
    emit_valid_pair_baseline,
)
from harness.events import EventLog
from harness.protocol import load
from harness.tree import Tree

ROOT = Path(__file__).resolve().parents[1]


def _pairwise_claim() -> Claim:
    return Claim(
        mechanism="pairwise",
        observables=[
            Observable("gauc_minus_ndcg_delta", "positive", "harness"),
            Observable("train_logloss", "up", "candidate"),
            Observable("valid_pairs_per_epoch", "positive", "candidate"),
        ],
    )


def test_attribution_is_computed_not_constant():
    assert not hasattr(Tree, "ATTRIBUTION_HAND")
    import harness.tree as tree_mod

    assert not hasattr(tree_mod, "ATTRIBUTION_HAND")


def test_all_observables_moved_is_clear():
    before = {
        "gauc_minus_ndcg_delta": 0.01,
        "train_logloss": 0.40,
        "valid_pairs_per_epoch": 100.0,
    }
    after = {
        "gauc_minus_ndcg_delta": 0.03,
        "train_logloss": 0.55,
        "valid_pairs_per_epoch": 140.0,
    }
    assert attribute(_pairwise_claim(), before, after) == "clear"


def test_partial_movement_is_unclear():
    before = {
        "gauc_minus_ndcg_delta": 0.01,
        "train_logloss": 0.40,
        "valid_pairs_per_epoch": 100.0,
    }
    after = {
        "gauc_minus_ndcg_delta": 0.03,
        "train_logloss": 0.55,
        "valid_pairs_per_epoch": 100.0,
    }
    assert attribute(_pairwise_claim(), before, after) == "unclear"


def test_missing_observable_is_unclear():
    before = {
        "gauc_minus_ndcg_delta": 0.01,
        "train_logloss": 0.40,
        "valid_pairs_per_epoch": 100.0,
    }
    after = {
        "gauc_minus_ndcg_delta": 0.03,
        "train_logloss": 0.55,
    }
    assert attribute(_pairwise_claim(), before, after) == "unclear"


def test_valid_pair_count_is_emitted(tmp_path: Path):
    proto = load(ROOT / "protocols" / "kuairand.yaml")
    events = EventLog(tmp_path / "run-pairs", "pairs", placeholder_protocol(tmp_path))
    try:
        emit_valid_pair_baseline(events, proto)
    finally:
        events.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / "run-pairs" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    pair_ev = [
        e
        for e in rows
        if e["type"] == "measurement" and e.get("metric") == "valid_pairs_per_epoch"
    ]
    assert pair_ev, "valid_pairs_per_epoch must be in the log before pairwise runs"
    assert pair_ev[0]["no_pair_pct"] == 42.2
    assert not any(e.get("mechanism") == "pairwise" for e in rows)
