"""Phase 5: pure measurement arithmetic and Measure event seams."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.measure import (
    LEAK_RULE_FEATURE,
    LEAK_RULE_GAIN,
    PROMOTE_FLOOR,
    Band,
    CalibrationError,
    Delta,
    HoldoutBudgetExceeded,
    Measure,
    MissingIncumbentSeed,
    RungMismatch,
    SeedCache,
    calibrate,
    combine_inconclusive,
    inconclusive_next,
    ladder_accepts,
    leak_audit,
    promote_bar,
    refresh_rho,
    replicate_verdict,
    screen_verdict,
)
from harness.types import Cost, Node, RunResult, Verdict

ROOT = Path(__file__).resolve().parents[1]


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
        seeds=[1],
        cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"),
        created_seq=1,
    )


def _result(
    seed: int,
    score: float,
    *,
    node: int = 1,
    rung: str = "screen",
) -> RunResult:
    return RunResult(
        node=node,
        attempt=1,
        seed=seed,
        rung=rung,  # type: ignore[arg-type]
        ok=True,
        metrics={"cvr_auc": score, "ctr_auc": 0.5},
        failure_class=None,
        stderr_tail="",
        gpu_s=0.0,
        wall_s=0.1,
        result_path=None,
        checkpoint_path=None,
    )


def _band(
    *,
    sigma_screen: float = 0.015,
    sigma_full: float = 0.012,
    rho: float = 0.5,
    source: str = "fixed_pair",
    n_replicated: int = 0,
) -> Band:
    sd_s = sigma_screen * math.sqrt(2.0 * (1.0 - rho))
    sd_f = sigma_full * math.sqrt(2.0 * (1.0 - rho))
    return Band(
        sigma_screen=sigma_screen,
        sigma_full=sigma_full,
        sigma_pair=0.0,
        ratio=sigma_full / sigma_screen,
        rho=rho,
        sd_delta_screen=sd_s,
        sd_delta_full=sd_f,
        bar=max(PROMOTE_FLOOR, 0.95 * sd_f),
        source=source,  # type: ignore[arg-type]
        n_replicated=n_replicated,
    )


def _series_with_stdev(target: float, n: int, mean: float = 0.55) -> list[float]:
    """Build n values with sample stdev ≈ target (n>=2)."""
    # One free point pattern: n-1 copies of mean, one outlier chosen for stdev.
    # sample variance = sum((x-m)^2)/(n-1). With mean fixed at `mean`:
    # use symmetric offsets.
    if n < 2:
        raise ValueError("n>=2")
    # For even n: ±a repeated; for odd: zeros + ±a
    # Simplest: values = mean + target * z where z has sample stdev 1.
    # z = [1, -1, 0, 0, ...] adjusted.
    raw = [0.0] * n
    raw[0] = 1.0
    raw[1] = -1.0
    # Current sample stdev of raw:
    m = sum(raw) / n
    var = sum((x - m) ** 2 for x in raw) / (n - 1)
    scale = target / math.sqrt(var)
    return [mean + scale * x for x in raw]


def _read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass
class FakeRunner:
    """Records runs; returns canned metrics keyed by (rung, seed) or a queue."""

    scores: dict[tuple[str, int], float] | None = None
    queue: list[float] | None = None
    calls: list[tuple[str, int]] | None = None
    run_cfg: dict | None = None

    def __post_init__(self) -> None:
        self.calls = []
        self.run_cfg = self.run_cfg or {"timeout_s": 30.0}
        self._qi = 0

    def run(self, node, rung, seed, timeout_s, env_overrides=None, attempt=1):
        del node, timeout_s, env_overrides, attempt
        assert self.calls is not None
        self.calls.append((rung, seed))
        if self.queue is not None:
            score = self.queue[self._qi]
            self._qi += 1
        else:
            assert self.scores is not None
            score = self.scores[(rung, seed)]
        return _result(seed, score, rung=rung)


def test_calibrate_columns():
    screen = _series_with_stdev(0.015, 5)
    full = _series_with_stdev(0.012, 3)
    # σ_pair 0.004 → |a−b| = 0.004√2
    half = 0.004 * math.sqrt(2.0) / 2.0
    pair_hi = (0.55 + half, 0.55 - half)
    band = calibrate(screen, full, pair_hi)
    assert band.sigma_screen == pytest.approx(0.015, abs=1e-9)
    assert band.sigma_full == pytest.approx(0.012, abs=1e-9)
    assert band.sigma_pair == pytest.approx(0.004, abs=1e-9)
    assert band.rho == 0.8
    assert band.sd_delta_screen == pytest.approx(0.0095, abs=0.00005)
    assert band.sd_delta_full == pytest.approx(0.0076, abs=0.00005)
    assert band.bar == pytest.approx(0.0100, abs=0.00005)
    assert band.ratio == pytest.approx(0.8, abs=1e-9)

    half2 = 0.010 * math.sqrt(2.0) / 2.0
    pair_lo = (0.55 + half2, 0.55 - half2)
    band2 = calibrate(screen, full, pair_lo)
    assert band2.rho == 0.5
    assert band2.sd_delta_screen == pytest.approx(0.0150, abs=0.00005)
    assert band2.sd_delta_full == pytest.approx(0.0120, abs=0.00005)
    assert band2.bar == pytest.approx(0.0114, abs=0.0003)
    assert band2.ratio == pytest.approx(0.8, abs=1e-9)


def test_calibrate_unstable_raises():
    screen = _series_with_stdev(0.015, 5)
    full_bad = _series_with_stdev(0.025, 3)
    pair = (0.55, 0.55)
    with pytest.raises(CalibrationError):
        calibrate(screen, full_bad, pair)

    screen_noisy = _series_with_stdev(0.025, 5)
    full_ok = _series_with_stdev(0.012, 3)
    band = calibrate(screen_noisy, full_ok, pair)
    assert band.sigma_full == pytest.approx(0.012, abs=1e-9)


def test_screen_table():
    band = _band(rho=0.5)
    assert band.sd_delta_screen == pytest.approx(0.015, abs=1e-9)
    assert screen_verdict(-0.011, band) == "rejected"
    assert screen_verdict(-0.010, band) == "rejected"
    assert screen_verdict(0.016, band) == "replicating"
    assert screen_verdict(0.015, band) == "replicating"
    assert screen_verdict(0.0149, band) == "inconclusive"
    assert screen_verdict(0.005, band) == "inconclusive"


def test_promote_bar():
    b1 = replace(_band(), sd_delta_full=0.0150)
    assert promote_bar(b1) == pytest.approx(0.01425)
    b2 = replace(_band(), sd_delta_full=0.0095)
    assert promote_bar(b2) == pytest.approx(0.010)
    b3 = replace(_band(), sd_delta_full=0.030)
    assert promote_bar(b3) == pytest.approx(0.0285)


def test_replicate_k3():
    band = replace(_band(), sd_delta_full=0.0150, bar=0.01425)
    assert band.bar == pytest.approx(0.01425)

    def D(vals):
        return [Delta(v, "replicate") for v in vals]

    assert replicate_verdict(D([0.03, 0.028, 0.032]), band) == "pass"
    assert replicate_verdict(D([0.012, 0.015, 0.018]), band) == "pass"
    assert replicate_verdict(D([0.011, 0.012, 0.013]), band) == "fail_mean"
    assert replicate_verdict(D([0.03, -0.001, 0.03]), band) == "fail_sign"
    assert replicate_verdict(D([0.03, 0.03]), band) == "fail_sign"


def test_replicate_refuses_screen_rung():
    band = _band()
    deltas = [
        Delta(0.03, "replicate"),
        Delta(0.03, "screen"),
        Delta(0.03, "replicate"),
    ]
    with pytest.raises(RungMismatch):
        replicate_verdict(deltas, band)


def test_leak_trigger():
    band = _band(rho=0.5)
    sd = band.sd_delta_full
    assert leak_audit(6.0 * sd, band, {}) == [LEAK_RULE_GAIN]
    assert leak_audit(0.0, band, {"f_x": 0.95}) == [LEAK_RULE_FEATURE]
    assert leak_audit(0.0, band, {"f_x": 0.85}) == []


def test_attribution_gate(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-attr", "attr", proto)
    try:
        band = _band(rho=0.5)
        # bar at ρ0.5, σ_full 0.012 → 0.0114; deltas well above
        measure = Measure(events, proto, band)
        inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
        results = [
            _result(1, 0.53, rung="replicate"),
            _result(2, 0.53, rung="replicate"),
            _result(3, 0.53, rung="replicate"),
        ]
        v_unclear = measure.verdict(
            _node(1), results, inc, "replicate", attribution="unclear"
        )
        assert v_unclear.state == "inconclusive"
        v_clear = measure.verdict(
            _node(2), results, inc, "replicate", attribution="clear"
        )
        assert v_clear.state == "promoted"
    finally:
        events.close()

    rows = _read_events(tmp_path / "run-attr")
    unclear_ev = [
        e
        for e in rows
        if e["type"] == "verdict" and e.get("attribution") == "unclear"
    ]
    assert len(unclear_ev) == 1
    assert unclear_ev[0]["state"] == "inconclusive"
    promoted = [e for e in rows if e["type"] == "incumbent_changed"]
    assert len(promoted) == 1
    assert promoted[0]["reason"] == "promotion"
    # unclear path must not emit incumbent_changed
    assert not any(
        e["type"] == "incumbent_changed" and e.get("node") == 1 for e in rows
    )


def test_ladder_eta():
    assert ladder_accepts(0.6500, 0.6551) is True
    assert ladder_accepts(0.6500, 0.6549) is False
    assert ladder_accepts(0.6500, 0.6500) is False


def test_holdout_budget(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-ho", "ho", proto)
    runner = FakeRunner(
        scores={("holdout", s): 0.56 for s in range(3)}
    )
    measure = Measure(events, proto, _band())
    inc = SeedCache({0: 0.55, 1: 0.55, 2: 0.55})
    try:
        r1 = measure.holdout_report(_node(), runner, inc, best_reported=0.50)
        r2 = measure.holdout_report(_node(), runner, inc, best_reported=0.50)
        assert r1.visit == 1 and r2.visit == 2
        calls_before = len(runner.calls or [])
        with pytest.raises(HoldoutBudgetExceeded):
            measure.holdout_report(_node(), runner, inc, best_reported=0.50)
        assert len(runner.calls or []) == calls_before
    finally:
        events.close()
    rows = _read_events(tmp_path / "run-ho")
    visits = [
        e["visit"]
        for e in rows
        if e["type"] == "measurement" and e.get("rung") == "holdout"
    ]
    assert visits == [1, 2]


def test_holdout_candidate_side_only(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-ho2", "ho2", proto)
    runner = FakeRunner(
        scores={("holdout", s): 0.56 + 0.001 * s for s in range(3)}
    )
    measure = Measure(events, proto, _band())
    inc = SeedCache({0: 0.55, 1: 0.55, 2: 0.55})
    try:
        report = measure.holdout_report(_node(), runner, inc, best_reported=0.50)
    finally:
        events.close()
    assert len(runner.calls or []) == 3
    assert all(rung == "holdout" for rung, _ in runner.calls or [])
    assert report.incumbent_scores == [0.55, 0.55, 0.55]
    assert len(report.candidate_scores) == 3


def test_inconclusive_revisits():
    assert inconclusive_next(0) == "requeue"
    assert inconclusive_next(1) == "requeue"
    assert inconclusive_next(2) == "retire"


def test_inconclusive_never_stacks():
    a = Verdict(
        node=1,
        rung="screen",
        state="inconclusive",
        metric="cvr_auc",
        delta_mean=0.0,
        delta_per_seed=[0.0],
        band=(-0.01, 0.01),
        reason="a",
        rule_trips=[],
    )
    b = replace(a, reason="b")
    assert combine_inconclusive(a, b) == "re_measure"


def test_verdict_pairs_by_seed(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-pair", "pair", proto)
    measure = Measure(events, proto, _band())
    # cache order different from results order
    inc = SeedCache({3: 0.50, 1: 0.50, 2: 0.50})
    results = [
        _result(1, 0.53, rung="replicate"),
        _result(2, 0.54, rung="replicate"),
        _result(3, 0.55, rung="replicate"),
    ]
    try:
        v = measure.verdict(_node(), results, inc, "replicate", attribution="clear")
        assert v.delta_per_seed == pytest.approx([0.03, 0.04, 0.05])
        with pytest.raises(MissingIncumbentSeed):
            measure.verdict(
                _node(2),
                [_result(2, 0.53, rung="screen")],
                SeedCache({1: 0.5}),
                "screen",
            )
    finally:
        events.close()


def test_rho_refresh(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-rho", "rho", proto)
    # Start at ρ=0.5; tight deltas → ρ rises, bar falls
    band = _band(rho=0.5)
    measure = Measure(events, proto, band)
    inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    tight = [
        _result(1, 0.53, rung="replicate"),
        _result(2, 0.5301, rung="replicate"),
        _result(3, 0.5299, rung="replicate"),
    ]
    try:
        for i in range(3):
            measure.verdict(
                _node(i + 1), tight, inc, "replicate", attribution="clear"
            )
        before = measure.band
        assert before is not None
        refreshed = measure.maybe_refresh()
        assert refreshed is not None
        assert refreshed.source == "refreshed"
        assert refreshed.rho > before.rho
        assert refreshed.bar < before.bar
        # fourth candidate + maybe_refresh does not re-emit
        measure.verdict(_node(4), tight, inc, "replicate", attribution="clear")
        assert measure.maybe_refresh() is None
    finally:
        events.close()
    rows = _read_events(tmp_path / "run-rho")
    refreshed_ev = [
        e
        for e in rows
        if e["type"] == "measurement"
        and e.get("stage") == "calibrate"
        and e.get("refreshed") is True
    ]
    assert len(refreshed_ev) == 1


def test_verdict_emits_event(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run-ve", "ve", proto)
    band = _band(rho=0.5)
    measure = Measure(events, proto, band)
    # Huge mean delta → leak trip
    inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    big = band.sd_delta_full * 6 + 0.50
    results = [
        _result(1, big, rung="replicate"),
        _result(2, big, rung="replicate"),
        _result(3, big, rung="replicate"),
    ]
    try:
        v = measure.verdict(_node(), results, inc, "replicate", attribution="clear")
        assert v.state == "leaked"
    finally:
        events.close()
    rows = _read_events(tmp_path / "run-ve")
    verdicts = [e for e in rows if e["type"] == "verdict"]
    assert len(verdicts) == 1
    ev = verdicts[0]
    assert "scores" in ev and "seeds" in ev and "band" in ev and "rung" in ev
    assert ev["rung"] == "replicate"
    assert isinstance(ev["band"], dict)
    trips = [e for e in rows if e["type"] == "rule_trip"]
    assert len(trips) == 1
    assert not any(e.get("rung") == "holdout" for e in rows if e["type"] == "verdict")
