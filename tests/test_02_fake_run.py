"""Phase 2: fake_run SCRIPT written through EventLog."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from harness.fake_run import SCRIPT, write
from harness.types import EVENT_TYPES

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fake-events.jsonl"

LEGAL = {
    "screening": frozenset({"running", "retired"}),
    "running": frozenset(
        {"replicating", "inconclusive", "rejected", "debugging", "retired"}
    ),
    "replicating": frozenset(
        {"promoted", "inconclusive", "rejected", "leaked", "retired"}
    ),
    "debugging": frozenset({"running", "retired"}),
    "promoted": frozenset({"retired"}),
    "inconclusive": frozenset({"retired"}),
    "rejected": frozenset({"retired"}),
    "leaked": frozenset({"retired"}),
    "retired": frozenset(),
}

NODE_REF_KEYS = ("node", "parent", "parent_node")


def _read_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return [json.loads(line) for line in text.splitlines()]


def _without_t(lines: list[dict]) -> list[dict]:
    out = []
    for ev in lines:
        item = dict(ev)
        item.pop("t", None)
        protocol = item.get("protocol")
        if isinstance(protocol, dict) and "protocol_path" in protocol:
            protocol = dict(protocol)
            # Absolute paths differ across machines; keep the filename only.
            protocol["protocol_path"] = Path(protocol["protocol_path"]).name
            item["protocol"] = protocol
        out.append(item)
    return out


@pytest.fixture
def fake_run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fake-0001"
    write(d, instant=True)
    return d


def test_covers_every_event_type(fake_run_dir: Path):
    events = _read_jsonl(fake_run_dir / "events.jsonl")
    beats = _read_jsonl(fake_run_dir / "heartbeat.jsonl")
    types = {ev["type"] for ev in events} | {ev["type"] for ev in beats}
    assert types == set(EVENT_TYPES)


def test_nodes_created_before_use(fake_run_dir: Path):
    events = _read_jsonl(fake_run_dir / "events.jsonl")
    seen: set[int] = set()
    for ev in events:
        if ev["type"] == "node_created":
            seen.add(ev["id"])
            parent = ev.get("parent")
            if parent is not None:
                assert parent in seen
            continue
        for key in NODE_REF_KEYS:
            if key not in ev:
                continue
            ref = ev[key]
            if ref is None:
                continue
            assert ref in seen, f"{ev['type']} seq={ev['seq']} {key}={ref} unseen"


def test_transitions_legal(fake_run_dir: Path):
    events = _read_jsonl(fake_run_dir / "events.jsonl")
    state: dict[int, str] = {}
    for ev in events:
        if ev["type"] == "node_created":
            state[ev["id"]] = "screening"
            continue
        if ev["type"] not in {"state_changed", "verdict"}:
            continue
        node = ev["node"]
        new = ev["state"]
        old = state[node]
        assert new in LEGAL[old], f"node {node}: {old}→{new} illegal"
        state[node] = new


def test_written_through_eventlog():
    src = (ROOT / "harness" / "fake_run.py").read_text(encoding="utf-8")
    # Strip comments so a mention in a comment does not fail the gate.
    stripped = re.sub(r"#.*", "", src)
    assert "open(" not in stripped
    assert "EventLog" in src


def test_summaries_are_sentences(fake_run_dir: Path):
    events = _read_jsonl(fake_run_dir / "events.jsonl")
    for ev in events:
        summary = ev["summary"]
        assert isinstance(summary, str)
        assert summary.strip()
        assert len(summary) < 140


def test_fixture_matches_regenerated(tmp_path: Path):
    run_dir = tmp_path / "fake-0001"
    write(run_dir, instant=True)
    generated = _without_t(_read_jsonl(run_dir / "events.jsonl"))
    assert FIXTURE.is_file(), f"missing fixture {FIXTURE}; generate with harness fake"
    fixture = _without_t(_read_jsonl(FIXTURE))
    assert generated == fixture


def test_script_starts_after_run_started():
    assert SCRIPT[0]["type"] == "hypothesis_queued"
    assert SCRIPT[-1]["type"] == "run_ended"
    assert all(ev["type"] != "run_started" for ev in SCRIPT)


def test_full_rung_verdicts_carry_attribution(fake_run_dir: Path):
    events = _read_jsonl(fake_run_dir / "events.jsonl")
    full = [
        e for e in events
        if e["type"] == "verdict" and e.get("rung") == "replicate"
    ]
    pairs = {(e.get("attribution"), e["state"]) for e in full}
    assert ("clear", "promoted") in pairs
    assert ("unclear", "inconclusive") in pairs
