"""Phase 9: audit projections over the fake run stream."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from harness.audit import (
    MixedProtocolError,
    assert_single_protocol,
    cost_by_slice,
    reliability,
    replication_pairs,
)
from harness.fake_run import write

ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def fake_events(tmp_path: Path) -> list[dict]:
    run_dir = tmp_path / "fake-0001"
    write(run_dir, instant=True)
    return _read_jsonl(run_dir / "events.jsonl")


def test_cost_slices_sum(fake_events: list[dict]):
    slices = cost_by_slice(fake_events)
    total_in = sum(s["tokens_in"] for s in slices.values())
    total_out = sum(s["tokens_out"] for s in slices.values())
    stream_in = sum(
        float(ev["cost"]["tokens_in"])
        for ev in fake_events
        if isinstance(ev.get("cost"), dict)
    )
    stream_out = sum(
        float(ev["cost"]["tokens_out"])
        for ev in fake_events
        if isinstance(ev.get("cost"), dict)
    )
    assert total_in == stream_in == 230
    assert total_out == stream_out == 90
    assert slices["training"]["gpu_h"] == pytest.approx(11.2 / 60.0)


def test_reliability_counts(fake_events: list[dict]):
    rel = reliability(fake_events)
    assert rel["failures_by_class"] == {"cuda_oom": 1, "stall": 1}
    assert rel["recoveries"] == {"ok": 2, "failed": 0}
    assert rel["rule_trips"] == 2


def test_longest_unattended(fake_events: list[dict]):
    rel = reliability(fake_events)
    interventions = [e for e in fake_events if e["type"] == "intervention"]
    assert len(interventions) == 1
    started = next(e for e in fake_events if e["type"] == "run_started")
    ended = next(e for e in fake_events if e["type"] == "run_ended")
    from harness.audit import _parse_ts

    t0 = _parse_ts(started["t"])
    ti = _parse_ts(interventions[0]["t"])
    t1 = _parse_ts(ended["t"])
    expected = max(ti - t0, t1 - ti)
    assert rel["longest_unattended_s"] == pytest.approx(expected)


def test_replication_pairs_per_node(fake_events: list[dict]):
    pairs = replication_pairs(fake_events)
    by_node = {row["node"]: row for row in pairs}
    assert 1 in by_node
    assert by_node[1]["searchval_vs_holdout"] is None
    assert sum(
        x is not None
        for x in (
            by_node[1]["screen_vs_full"],
            by_node[1]["one_vs_many_seeds"],
            by_node[1]["searchval_vs_holdout"],
        )
    ) == 0
    assert 3 in by_node
    assert all(
        by_node[3][k] is not None
        for k in ("screen_vs_full", "one_vs_many_seeds", "searchval_vs_holdout")
    )


def test_refuse_mixed_hashes(fake_events: list[dict]):
    other = [dict(e, protocol_hash="sha256:deadbeef") for e in fake_events[:5]]
    with pytest.raises(MixedProtocolError):
        assert_single_protocol(fake_events + other)


def test_endpoints(fake_events: list[dict], tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "fake-0001"
    write(run_dir, instant=True)
    monkeypatch.setattr("app.server.RUNS", tmp_path / "runs")
    from app.server import app

    client = TestClient(app)
    events = _read_jsonl(run_dir / "events.jsonl")
    rid = run_dir.name
    assert client.get(f"/runs/{rid}/audit/replication").json() == replication_pairs(
        events
    )
    assert client.get(f"/runs/{rid}/audit/cost").json() == cost_by_slice(events)
    assert client.get(f"/runs/{rid}/audit/reliability").json() == reliability(events)
