"""Step 10: attribution is a function of declared observables, not a constant."""

from __future__ import annotations

import json
import math
from pathlib import Path

from helpers import placeholder_protocol
from harness.attribute import (
    Claim,
    Observable,
    attribute,
    emit_valid_pair_baseline,
)
from harness.events import EventLog
from harness.measure import PROMOTE_FLOOR, Band, Measure, SeedCache
from harness.protocol import load
from harness.tree import Tree
from harness.types import Cost, Node, RunResult

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


def test_attribution_is_computed_not_constant(tmp_path: Path):
    assert not hasattr(Tree, "ATTRIBUTION_HAND")
    import harness.tree as tree_mod

    assert not hasattr(tree_mod, "ATTRIBUTION_HAND")

    before = {
        "gauc_minus_ndcg_delta": 0.01,
        "train_logloss": 0.40,
        "valid_pairs_per_epoch": 100.0,
    }
    after_all = {
        "gauc_minus_ndcg_delta": 0.03,
        "train_logloss": 0.55,
        "valid_pairs_per_epoch": 140.0,
    }
    after_stuck = {
        "gauc_minus_ndcg_delta": 0.03,
        "train_logloss": 0.55,
        "valid_pairs_per_epoch": 100.0,
    }
    claim = _pairwise_claim()
    computed_clear = attribute(claim, before, after_all)
    computed_unclear = attribute(claim, before, after_stuck)
    assert computed_clear == "clear"
    assert computed_unclear == "unclear"

    rho = 0.5
    sigma_full = 0.012
    sd_f = sigma_full * math.sqrt(2.0 * (1.0 - rho))
    band = Band(
        sigma_screen=0.015,
        sigma_full=sigma_full,
        sigma_pair=0.0,
        ratio=sigma_full / 0.015,
        rho=rho,
        sd_delta_screen=0.015 * math.sqrt(2.0 * (1.0 - rho)),
        sd_delta_full=sd_f,
        bar=max(PROMOTE_FLOOR, 0.95 * sd_f),
        source="fixed_pair",
        n_replicated=0,
    )
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-attr-const", "attrc", proto)
    results = [
        RunResult(
            node=1, attempt=1, seed=s, rung="replicate", ok=True,
            metrics={"cvr_auc": 0.53}, failure_class=None, stderr_tail="",
            gpu_s=0.0, wall_s=0.1, result_path=None, checkpoint_path=None,
        )
        for s in (1, 2, 3)
    ]
    inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    try:
        measure = Measure(events, proto, band, metric="cvr_auc")
        v_clear = measure.verdict(
            Node(
                id=1, parent=None, hypothesis_id="h-a", commit=None,
                state="running", rung="replicate", kind="draft",
                scores={}, seeds=[], cost=Cost(0.0, 0, 0, "training"),
                created_seq=1,
            ),
            results, inc, "replicate", attribution=computed_clear,
        )
        v_unclear = measure.verdict(
            Node(
                id=2, parent=None, hypothesis_id="h-b", commit=None,
                state="running", rung="replicate", kind="draft",
                scores={}, seeds=[], cost=Cost(0.0, 0, 0, "training"),
                created_seq=2,
            ),
            results, inc, "replicate", attribution=computed_unclear,
        )
        assert v_clear.state == "promoted"
        assert v_unclear.state == "inconclusive"
    finally:
        events.close()


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
