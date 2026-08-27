"""Phase 2: FastAPI event / heartbeat replay server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from harness.fake_run import write
from harness.protocol import load

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "runs"
    d.mkdir()
    import app.server as server

    monkeypatch.setattr(server, "RUNS", d)
    write(d / "fake-0001", instant=True)
    return d


@pytest.fixture
def client(runs_dir: Path) -> TestClient:
    from app.server import app

    return TestClient(app)


def test_list_runs(client: TestClient):
    protocol = load(ROOT / "protocols" / "synthetic.yaml")
    res = client.get("/runs")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "fake-0001"
    assert row["protocol_hash"] == protocol.protocol_hash
    assert row["task"] == "synthetic"
    assert row["started"]


def test_replay_from_zero(client: TestClient, runs_dir: Path):
    res = client.get("/runs/fake-0001/events", params={"since": 0, "stream": False})
    assert res.status_code == 200
    lines = res.json()
    on_disk = [
        json.loads(line)
        for line in (runs_dir / "fake-0001" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert lines == on_disk
    assert [ev["seq"] for ev in lines] == list(range(1, len(lines) + 1))


def test_since_filters(client: TestClient):
    res = client.get("/runs/fake-0001/events", params={"since": 100, "stream": False})
    assert res.status_code == 200
    lines = res.json()
    assert lines
    assert all(ev["seq"] > 100 for ev in lines)


def test_sse_frames(runs_dir: Path, client: TestClient):
    from app.server import _sse_tail, get_events
    from starlette.requests import Request

    on_disk = [
        json.loads(line)
        for line in (runs_dir / "fake-0001" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    n = min(20, len(on_disk))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/runs/fake-0001/events",
        "raw_path": b"/runs/fake-0001/events",
        "query_string": b"stream=true",
        "headers": [],
        "client": ("test", 50000),
        "server": ("test", 80),
    }
    wired = get_events(
        "fake-0001", since=0, stream=True, request=Request(scope)
    )
    assert wired.media_type == "text/event-stream"

    async def _collect() -> list[dict]:
        request = AsyncMock()
        request.is_disconnected = AsyncMock(return_value=False)
        got: list[dict] = []
        gen = _sse_tail(runs_dir / "fake-0001" / "events.jsonl", 0, request)
        try:
            async for chunk in gen:
                text = chunk.decode("utf-8")
                assert text.startswith("data: ")
                assert text.endswith("\n\n")
                got.append(json.loads(text[len("data: ") :].strip()))
                if len(got) >= n:
                    break
        finally:
            await gen.aclose()
        return got

    got = asyncio.run(_collect())
    assert got == on_disk[:n]


def test_tail_picks_up_new_line(runs_dir: Path):
    from app.server import _sse_tail

    path = runs_dir / "fake-0001" / "events.jsonl"
    existing = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    last_seq = existing[-1]["seq"]
    protocol_hash = existing[-1]["protocol_hash"]
    new_ev = {
        "schema_version": 1,
        "seq": last_seq + 1,
        "t": "2099-01-01T00:00:00.000Z",
        "run": "fake-0001",
        "protocol_hash": protocol_hash,
        "type": "intervention",
        "summary": "tail probe line",
    }

    async def _run() -> list[dict]:
        request = AsyncMock()
        request.is_disconnected = AsyncMock(return_value=False)
        gen = _sse_tail(path, last_seq, request)
        seen: list[dict] = []

        async def _consume() -> None:
            async for chunk in gen:
                text = chunk.decode("utf-8")
                assert text.startswith("data: ")
                seen.append(json.loads(text[len("data: ") :].strip()))
                return

        task = asyncio.create_task(_consume())
        await asyncio.sleep(0.2)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(new_ev, separators=(",", ":")) + "\n")
            fh.flush()
        await asyncio.wait_for(task, timeout=2.0)
        await gen.aclose()
        return seen

    seen = asyncio.run(_run())
    assert seen and seen[0]["seq"] == last_seq + 1
    assert seen[0]["summary"] == "tail probe line"


def test_unknown_run_404(client: TestClient):
    res = client.get("/runs/does-not-exist/events", params={"stream": False})
    assert res.status_code == 404
    res = client.get("/runs/does-not-exist/heartbeat", params={"stream": False})
    assert res.status_code == 404
