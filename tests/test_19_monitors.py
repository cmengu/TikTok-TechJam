"""Step 12: overfitting monitors and the derived claim are folds over the log."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from harness.overfit import (
    gap_alarm,
    ladder_queries,
    oracle_gap,
    seed_consistency,
    split_rank_corr,
)
from harness.outputs import claim_level, report

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


def test_seed_sign_flip_downgrades():
    assert seed_consistency([0.02, 0.03, 0.01]) == 1.0
    flipped = seed_consistency([0.02, 0.03, -0.01])
    assert flipped == 2 / 3
    assert flipped < 1.0


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
