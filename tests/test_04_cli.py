"""Phase 4: ``python -m harness run-one`` drives one real node through a real EventLog."""

from __future__ import annotations

import json
from pathlib import Path

from harness.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_run_one_emits_heartbeat_and_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main([
        "run-one", "--protocol", str(ROOT / "protocols" / "synthetic.yaml"),
        "--rows", "50000", "--fail", "nan", "--heartbeat", "0.5", "--timeout", "120",
    ])
    out = capsys.readouterr().out
    run_id = next(l.split("=", 1)[1] for l in out.splitlines() if l.startswith("run_id="))
    run_dir = tmp_path / "runs" / run_id

    events = _read_jsonl(run_dir / "events.jsonl")
    heartbeats = _read_jsonl(run_dir / "heartbeat.jsonl")
    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert "failure" in types
    assert any(e.get("class") == "diverged" for e in events if e["type"] == "failure")
    assert "recovery" not in types  # diverged is abandoned, never retried
    assert len(heartbeats) >= 1
    assert "failure_class=diverged" in out
