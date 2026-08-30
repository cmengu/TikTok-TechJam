"""Step 8: numeric provenance — only the measurement layer may report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.events import EventLog, MEASURED, NumericProvenanceError, ForecastProvenanceError
from harness.protocol import load

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "protocols" / "synthetic.yaml"


@pytest.fixture
def protocol():
    return load(SYNTHETIC)


@pytest.fixture
def log(tmp_path: Path, protocol):
    events = EventLog(tmp_path / "run", "prov", protocol)
    yield events
    events.close()


def _read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_agent_cannot_emit_a_metric(log, tmp_path):
    with pytest.raises(NumericProvenanceError) as exc:
        log.emit("measurement", summary="agent leak", delta_mean=0.01, producer="researcher")
    assert "delta_mean" in exc.value.args[0]
    rows = [e for e in _read_events(tmp_path / "run") if e["type"] == "measurement"]
    assert rows == []


def test_measure_can_emit_a_metric(log, tmp_path):
    log.emit("verdict", summary="from task.score", delta_mean=0.02, producer="measure")
    log.drain()
    rows = [e for e in _read_events(tmp_path / "run") if e["type"] == "verdict"]
    assert rows[-1]["delta_mean"] == 0.02
    assert rows[-1]["producer"] == "measure"


def test_expected_gain_never_enters_a_verdict(log):
    with pytest.raises(ForecastProvenanceError) as exc:
        log.emit(
            "verdict",
            summary="forecast leaked into verdict",
            expected_gain=0.01,
            producer="measure",
        )
    assert "expected_gain" in exc.value.args[0]


def test_fake_run_does_not_exempt_provenance():
    src = (ROOT / "harness" / "fake_run.py").read_text(encoding="utf-8")
    assert "setdefault" not in src
    assert "producer" in src


def test_every_number_in_a_run_has_a_producer(tmp_path: Path):
    run_dir = tmp_path / "runs" / "fake-0001"
    subprocess.run(
        [sys.executable, "-m", "harness", "fake", "--instant", "--run-id", "fake-0001"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    events = _read_events(run_dir)
    assert events, "fake --instant wrote no events"
    orphans = [
        (e["type"], e["seq"], sorted(MEASURED & e.keys()))
        for e in events
        if (MEASURED & e.keys()) and e.get("producer") != "measure"
    ]
    assert orphans == []
