"""Step 5: ladder thresholds are expressions of a measured σ and organiser ε."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.events import EventLog
from harness.measure import Band, Delta, Measure, replicate_verdict


@pytest.fixture(autouse=True)
def _restore_thresholds():
    import harness.measure as m

    old = (m.SIGMA_UNSTABLE, m.SCREEN_REJECT_DELTA, m.PROMOTE_FLOOR, m.LADDER_ETA)
    yield
    m.SIGMA_UNSTABLE, m.SCREEN_REJECT_DELTA, m.PROMOTE_FLOOR, m.LADDER_ETA = old


def _proto_with_sigma(tmp_path: Path, sigma: float):
    raw = yaml.safe_load((Path(__file__).resolve().parents[1] / "protocols" / "kuairand.yaml").read_text())
    raw["ruler"]["calibration"]["sigma"] = sigma
    path = tmp_path / "calib.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    from harness.protocol import load

    return load(path)


def test_thresholds_derive_from_sigma(tmp_path: Path):
    proto = _proto_with_sigma(tmp_path, 0.0004)
    events = EventLog(tmp_path / "run", "cal", proto)
    try:
        Measure(events, proto, None, metric="primary")
    finally:
        events.close()
    from harness import measure as m

    assert m.SIGMA_UNSTABLE == pytest.approx(6.0 * 0.0004)
    assert m.SCREEN_REJECT_DELTA == pytest.approx(-2.0 * 0.0004)
    assert m.PROMOTE_FLOOR == pytest.approx(2.0 * 0.0004)
    assert m.LADDER_ETA == pytest.approx(0.002)


def test_epsilon_and_n_are_not_derived(tmp_path: Path):
    proto = _proto_with_sigma(tmp_path, 0.0004)
    assert proto.ruler["convergence"]["epsilon"] == 0.002
    assert proto.ruler["convergence"]["n_rounds"] == 3
    events = EventLog(tmp_path / "run", "cal", proto)
    try:
        Measure(events, proto, None, metric="primary")
    finally:
        events.close()
    from harness import measure as m

    assert m.LADDER_ETA == proto.ruler["convergence"]["epsilon"]
    src = (Path(__file__).resolve().parents[1] / "harness" / "measure.py").read_text()
    assert "0.0008" not in src


def test_noise_sized_delta_does_not_promote(tmp_path: Path):
    proto = _proto_with_sigma(tmp_path, 0.0004)
    events = EventLog(tmp_path / "run", "cal", proto)
    try:
        Measure(events, proto, None, metric="primary")
    finally:
        events.close()
    from harness import measure as m

    sigma = 0.0004
    # 1σ delta is below the 2σ promote floor
    assert 1.0 * sigma < m.PROMOTE_FLOOR
    band = Band(
        sigma_screen=sigma,
        sigma_full=sigma,
        sigma_pair=sigma,
        ratio=1.0,
        rho=0.8,
        sd_delta_screen=sigma,
        sd_delta_full=sigma,
        bar=m.PROMOTE_FLOOR,
        source="test",
        n_replicated=0,
    )
    tagged = [Delta(value=1.0 * sigma, rung="replicate") for _ in range(3)]
    assert replicate_verdict(tagged, band) != "pass"


def test_real_delta_promotes(tmp_path: Path):
    proto = _proto_with_sigma(tmp_path, 0.0004)
    events = EventLog(tmp_path / "run", "cal", proto)
    try:
        Measure(events, proto, None, metric="primary")
    finally:
        events.close()
    from harness import measure as m

    sigma = 0.0004
    band = Band(
        sigma_screen=sigma,
        sigma_full=sigma,
        sigma_pair=sigma,
        ratio=1.0,
        rho=0.8,
        sd_delta_screen=sigma,
        sd_delta_full=sigma,
        bar=m.PROMOTE_FLOOR,
        source="test",
        n_replicated=0,
    )
    tagged = [Delta(value=4.0 * sigma, rung="replicate") for _ in range(3)]
    assert replicate_verdict(tagged, band) == "pass"
