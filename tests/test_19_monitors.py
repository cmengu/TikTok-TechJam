"""Step 12: overfitting monitors and the derived claim are folds over the log."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.measure import PROMOTE_FLOOR, Measure, SeedCache
from harness.overfit import (
    gap_alarm,
    ladder_queries,
    oracle_gap,
    seed_consistency,
    split_rank_corr,
)
from harness.outputs import claim_level, claim_reason, report
from harness.types import Cost, Node, RunResult

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fake-events.jsonl"


def _load_fixture() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _promo(node: int, delta_mean: float, oracle_delta: float | None) -> dict:
    ev: dict = {
        "type": "verdict",
        "state": "promoted",
        "node": node,
        "delta_mean": delta_mean,
        "delta_per_seed": [delta_mean, delta_mean, delta_mean],
    }
    if oracle_delta is not None:
        ev["oracle_delta"] = oracle_delta
    return ev


def test_oracle_gap_is_a_fold():
    events = [
        _promo(1, 0.030, 0.010),
        {"type": "verdict", "state": "rejected", "node": 2, "delta_mean": 0.0},
        _promo(3, 0.040, 0.015),
    ]
    first = oracle_gap(events)
    second = oracle_gap(events)
    assert first[0][0] == 1 and first[1][0] == 3
    assert first[0][1] == pytest.approx(0.020)
    assert first[1][1] == pytest.approx(0.025)
    assert first == second


def test_gap_alarm_needs_three_promotions():
    two = [_promo(1, 0.03, 0.02), _promo(2, 0.05, 0.03)]
    assert gap_alarm(two) is False
    widening = [
        _promo(1, 0.03, 0.02),
        _promo(2, 0.05, 0.03),
        _promo(3, 0.08, 0.04),
    ]
    gaps = [g for _, g in oracle_gap(widening)]
    assert gaps[0] == pytest.approx(0.01)
    assert gaps[1] == pytest.approx(0.02)
    assert gaps[2] == pytest.approx(0.04)
    assert gap_alarm(widening) is True
    shrinking = [
        _promo(1, 0.08, 0.04),
        _promo(2, 0.05, 0.03),
        _promo(3, 0.03, 0.02),
    ]
    assert gap_alarm(shrinking) is False


def test_rank_corr_returns_none_below_three():
    fixture = _load_fixture()
    assert split_rank_corr(fixture) is None
    assert split_rank_corr([_promo(1, 0.03, 0.01), _promo(2, 0.04, 0.02)]) is None
    three = [
        _promo(1, 0.01, 0.01),
        _promo(2, 0.02, 0.02),
        _promo(3, 0.03, 0.03),
    ]
    rho = split_rank_corr(three)
    assert rho is not None
    assert rho == pytest.approx(1.0)


def _node(nid: int = 1) -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id="h-m",
        commit=None,
        state="running",
        rung="screen",
        kind="draft",
        scores={},
        seeds=[],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=nid,
    )


def _result(seed: int, score: float) -> RunResult:
    return RunResult(
        node=1,
        attempt=1,
        seed=seed,
        rung="replicate",
        ok=True,
        metrics={"cvr_auc": score},
        failure_class=None,
        stderr_tail="",
        gpu_s=0.0,
        wall_s=0.1,
        result_path=None,
        checkpoint_path=None,
    )


def _band():
    from harness.measure import Band

    rho = 0.5
    sigma_full = 0.012
    sd_f = sigma_full * math.sqrt(2.0 * (1.0 - rho))
    return Band(
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


def test_seed_sign_flip_downgrades(tmp_path: Path):
    assert seed_consistency([0.02, 0.03, 0.01]) == 1.0
    flipped = seed_consistency([0.02, 0.03, -0.01])
    assert flipped == 2 / 3
    assert flipped < 1.0

    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-flip", "flip", proto)
    inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    # Mixed signs: replicate_verdict would fail_sign; the monitor routes to
    # inconclusive (then retire on the third visit of the same node).
    mixed = [_result(1, 0.52), _result(2, 0.53), _result(3, 0.49)]
    try:
        measure = Measure(events, proto, _band(), metric="cvr_auc")
        node = _node(1)
        first = measure.verdict(node, mixed, inc, "replicate", attribution="clear")
        second = measure.verdict(node, mixed, inc, "replicate", attribution="clear")
        third = measure.verdict(node, mixed, inc, "replicate", attribution="clear")
        assert first.state == "inconclusive"
        assert second.state == "inconclusive"
        assert third.state == "retired"
    finally:
        events.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / "run-flip" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    states = [e["state"] for e in rows if e["type"] == "verdict"]
    assert states == ["inconclusive", "inconclusive", "retired"]


def test_gap_alarm_blocks_promotion_without_oracle_gain(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-gap", "gap", proto)
    inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    passing = [_result(1, 0.53), _result(2, 0.53), _result(3, 0.53)]
    try:
        measure = Measure(events, proto, _band(), metric="cvr_auc")
        widening = [(1, 0.02), (2, 0.01), (3, 0.00)]
        for nid, oracle in widening:
            v = measure.verdict(
                _node(nid), passing, inc, "replicate",
                attribution="clear", oracle_delta=oracle,
            )
            assert v.state == "promoted"
        blocked = measure.verdict(
            _node(4), passing, inc, "replicate",
            attribution="clear", oracle_delta=0.0,
        )
        assert blocked.state == "rejected"
        allowed = measure.verdict(
            _node(5), passing, inc, "replicate",
            attribution="clear", oracle_delta=0.01,
        )
        assert allowed.state == "promoted"
    finally:
        events.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / "run-gap" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    by_node = {e["node"]: e["state"] for e in rows if e["type"] == "verdict"}
    assert by_node[4] == "rejected"
    assert by_node[5] == "promoted"


def test_ladder_queries_matches_promotions():
    events = [_promo(1, 0.03, 0.01), _promo(2, 0.04, 0.02)]
    assert ladder_queries(events) == 2
    assert ladder_queries(_load_fixture()) == 1


def test_claim_downgrades_without_oracle(tmp_path: Path):
    events = _load_fixture()
    assert claim_level(events) == "L4-v"
    stripped = copy.deepcopy(events)
    for ev in stripped:
        ev.pop("oracle_delta", None)
    assert claim_level(stripped) == "L4-m"
    assert claim_level([]) == "L3"
    out = tmp_path / "report.md"
    numbers = report(stripped, out)
    assert set(numbers) >= {"primary", "spread", "oracle_gap", "ladder_queries"}
    assert numbers["ladder_queries"] == 1
    text = out.read_text(encoding="utf-8")
    assert "primary" in text
    assert "L4-v" not in text


def test_claim_reason_counts_promotions_carrying_oracle_delta():
    events = _load_fixture()
    assert claim_level(events) == "L4-v"
    assert claim_reason(events) == "1 of 1 promotions carry oracle_delta"


def test_claim_reason_shows_the_downgrade():          # refusal twin
    events = [_promo(1, 0.03, 0.01), _promo(2, 0.04, None)]
    assert claim_level(events) == "L4-m"
    assert claim_reason(events) == "1 of 2 promotions carry oracle_delta"


def test_claim_reason_without_promotions():           # refusal twin
    assert claim_level([]) == "L3"
    reason = claim_reason([])
    assert "promotion" in reason
    assert "L4" not in reason                         # the sentence never claims a rung


def test_claim_reason_is_a_pure_fold():
    events = _load_fixture()
    before = copy.deepcopy(events)
    assert claim_reason(events) == claim_reason(events)
    assert events == before                           # the fold does not touch its input
