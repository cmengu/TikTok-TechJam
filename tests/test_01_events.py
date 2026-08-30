"""Phase 1: single-writer event log."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from harness.events import EventLog
from harness.protocol import load

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "protocols" / "synthetic.yaml"

STAMP_KEYS = ("schema_version", "seq", "t", "run", "protocol_hash", "type", "summary")


@pytest.fixture
def protocol():
    return load(SYNTHETIC)


@pytest.fixture
def run_dir(tmp_path: Path, protocol):
    d = tmp_path / "run"
    d.mkdir()
    return d


def _events_path(run_dir: Path) -> Path:
    return run_dir / "events.jsonl"


def _heartbeat_path(run_dir: Path) -> Path:
    return run_dir / "heartbeat.jsonl"


def _read_lines(path: Path) -> list[dict]:
    text = path.read_text()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def test_first_line_is_run_started(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    log.close()
    lines = _read_lines(_events_path(run_dir))
    assert len(lines) == 1
    ev = lines[0]
    assert ev["type"] == "run_started"
    assert ev["protocol_hash"] == protocol.protocol_hash
    body = ev["protocol"]
    assert body["schema_version"] == protocol.schema_version
    assert body["task"] == protocol.task
    assert body["ruler"] == protocol.ruler
    assert body["run"] == protocol.run
    assert body["protocol_hash"] == protocol.protocol_hash
    assert body["protocol_path"] == str(protocol.path)
    assert not any(k.startswith("_") for k in body)


def test_concurrent_emit_no_torn_lines(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            for i in range(1000):
                log.emit("measurement", summary=f"w{n}-{i}", worker=f"w{n}")
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log.close()
    assert not errors
    lines = _read_lines(_events_path(run_dir))
    assert len(lines) == 3001
    seqs = [ev["seq"] for ev in lines]
    assert seqs == list(range(1, 3002))


def test_stamps_present(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    log.emit("measurement", summary="a")
    log.emit("verdict", summary="b", state="promoted")
    log.close()
    for ev in _read_lines(_events_path(run_dir)):
        for key in STAMP_KEYS:
            assert key in ev
        assert ev["schema_version"] == 1
        assert isinstance(ev["seq"], int)
        assert ev["t"].endswith("Z")
        assert ev["run"] == "synthetic-test"
        assert ev["protocol_hash"] == protocol.protocol_hash
        assert isinstance(ev["summary"], str)


def test_unknown_type_raises(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    with pytest.raises(ValueError):
        log.emit("failed", summary="nope")
    log.close()
    assert len(_read_lines(_events_path(run_dir))) == 1


def test_heartbeat_via_emit_raises(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    with pytest.raises(ValueError, match="heartbeat"):
        log.emit("heartbeat", summary="nope", worker="w1")
    log.close()
    assert len(_read_lines(_events_path(run_dir))) == 1
    assert _read_lines(_heartbeat_path(run_dir)) == []


def test_bad_state_raises(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    with pytest.raises(ValueError):
        log.emit("state_changed", state="nope", summary="bad")
    log.close()
    assert len(_read_lines(_events_path(run_dir))) == 1


def test_missing_summary_raises(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    with pytest.raises(ValueError):
        log.emit("measurement")
    log.close()


def test_heartbeat_sidecar(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    for i in range(10):
        log.heartbeat("w1", progress=i)
    log.close()
    # Heartbeats must not move events.jsonl (still only run_started).
    assert len(_read_lines(_events_path(run_dir))) == 1
    beats = _read_lines(_heartbeat_path(run_dir))
    assert len(beats) == 10
    assert [b["seq"] for b in beats] == list(range(1, 11))
    for b in beats:
        assert b["type"] == "heartbeat"
        assert b["schema_version"] == 1
        assert b["run"] == "synthetic-test"
        assert b["protocol_hash"] == protocol.protocol_hash
        assert b["worker"] == "w1"
        assert "summary" not in b


def test_new_node_unique_under_threads(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    ids: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        local = [log.new_node(None) for _ in range(500)]
        with lock:
            ids.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log.close()
    assert len(ids) == 2000
    assert len(set(ids)) == 2000


def test_close_drains_then_refuses(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    for i in range(50):
        log.emit("measurement", summary=str(i))
    log.close()
    assert len(_read_lines(_events_path(run_dir))) == 51
    with pytest.raises(RuntimeError):
        log.emit("measurement", summary="after close")


def test_seq_monotonic_same_millisecond(run_dir, protocol):
    log = EventLog(run_dir, "synthetic-test", protocol)
    for i in range(100):
        log.emit("measurement", summary=str(i))
    log.close()
    lines = _read_lines(_events_path(run_dir))
    seqs = [ev["seq"] for ev in lines]
    # run_started + 100 emits
    assert seqs == list(range(1, 102))
    # seq strictly increases even where t repeats
    for a, b in zip(lines, lines[1:]):
        assert b["seq"] > a["seq"]
