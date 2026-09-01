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


MONITORS_KEYS = {
    "available",
    "primary",
    "spread",
    "oracle_gap",
    "gap_alarm",
    "seed_consistency",
    "rank_corr",
    "ladder_queries",
    "claim_level",
    "claim_reason",
    "holdout_visits",
    "holdout_cap",
    "digests_ok",
}


def test_monitors_returns_every_contract_key(client: TestClient):
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == MONITORS_KEYS
    assert body["claim_level"] == "L4-v"


def test_monitors_numbers_come_from_the_harness_folds(client: TestClient, runs_dir: Path):
    from harness.overfit import headline, oracle_gap

    events = [
        json.loads(line)
        for line in (runs_dir / "fake-0001" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    primary, spread = headline(events)
    assert body["primary"] == primary
    assert body["spread"] == spread
    assert body["oracle_gap"] == [list(row) for row in oracle_gap(events)]


def test_monitors_rank_corr_is_null_below_three_promotions(client: TestClient):
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    assert body["rank_corr"] is None
    assert body["rank_corr"] != 0
    assert body["rank_corr"] != 0.0


def test_monitors_gap_alarm_false_on_a_healthy_run(client: TestClient):
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    assert res.json()["gap_alarm"] is False


def test_monitors_is_available_false_not_500_without_overfit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import sys

    monkeypatch.setitem(sys.modules, "harness.overfit", None)
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "harness.overfit" in body["reason"]


def test_monitors_unknown_run_is_404(client: TestClient):
    res = client.get("/runs/does-not-exist/audit/monitors")
    assert res.status_code == 404


def test_brief_returns_sections(client: TestClient):
    res = client.get("/runs/fake-0001/brief")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["task"] == "synthetic"
    assert isinstance(body["sections"], list)
    assert len(body["sections"]) >= 1
    assert "title" in body["sections"][0]
    assert "body" in body["sections"][0]


def test_brief_missing_available_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import app.server as server

    monkeypatch.setattr(server, "BRIEF_PATH", tmp_path / "missing.md")
    res = client.get("/runs/fake-0001/brief")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "brief" in body["reason"]


def test_brief_unknown_run_404(client: TestClient):
    res = client.get("/runs/does-not-exist/brief")
    assert res.status_code == 404


def test_manifest_serves_and_validates(client: TestClient):
    import app.server as server

    res = client.get("/papers/manifest")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    papers = body["papers"]
    assert isinstance(papers, list)
    assert len(papers) >= 1
    for entry in papers:
        assert entry.get("url") or entry.get("pdf"), entry
        pdf = entry.get("pdf")
        if pdf:
            path = server.PAPERS / pdf
            assert path.is_file(), f"missing pdf {pdf}"


def test_pdf_static_mount(client: TestClient):
    import app.server as server

    pdf = server.PAPERS / "_probe.pdf"
    pdf.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<>\n%%EOF\n")
    try:
        res = client.get("/papers/_probe.pdf")
        assert res.status_code == 200
        assert "application/pdf" in res.headers.get("content-type", "")
    finally:
        pdf.unlink(missing_ok=True)


def test_manifest_malformed_degrades(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import app.server as server

    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(server, "PAPERS", tmp_path)
    res = client.get("/papers/manifest")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "malformed" in body.get("reason", "")


def test_report_serves_markdown(client: TestClient, runs_dir: Path):
    (runs_dir / "fake-0001" / "report.md").write_text(
        "# Run report\n\nHello from the summary.\n", encoding="utf-8"
    )
    res = client.get("/runs/fake-0001/report")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert "Hello from the summary" in body["markdown"]


def test_report_absent_available_false(client: TestClient):
    res = client.get("/runs/fake-0001/report")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "finished" in body["reason"]


def test_contract_returns_rules(client: TestClient):
    res = client.get("/contract")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    rules = body["rules"]
    # Addendum said nine; candidate/rules.jsonl has 18. The file is right.
    assert len(rules) == 18
    for row in rules:
        assert "id" in row
        assert "statement" in row
        assert "check" in row
        assert "severity" in row


def test_contract_malformed_degrades(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    bad = tmp_path / "rules.jsonl"
    bad.write_text("{not json\n", encoding="utf-8")
    import harness.verify as verify

    monkeypatch.setattr(verify, "RULES_PATH", bad)
    res = client.get("/contract")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "the contract file is unreadable"


def test_monitors_carries_wall_fields(client: TestClient):
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    assert "holdout_visits" in body
    assert body["holdout_cap"] == 12
    assert body["holdout_visits"] >= 0
    assert "digests_ok" in body


def test_wall_fields_zero_when_no_holdout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import app.server as server

    monkeypatch.setattr(server, "_read_jsonl", lambda path: [])
    res = client.get("/runs/fake-0001/audit/monitors")
    assert res.status_code == 200
    body = res.json()
    assert body["holdout_visits"] == 0
    assert body["holdout_cap"] == 12


def test_feedback_missing_degrades(client: TestClient):
    res = client.get("/runs/fake-0001/feedback")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "no failures yet" in body["reason"]


def test_feedback_endpoint_shape(client: TestClient, runs_dir: Path):
    from harness.feedback import write_lesson, feedback_from, load_lessons, render

    path = runs_dir / "fake-0001" / "lessons.jsonl"
    write_lesson(
        path,
        {
            "round": 1,
            "node": 2,
            "family": "features/crossed-ids",
            "pattern": "crossed-ids",
            "defect": "no_gain",
            "delta": -0.002,
            "verdict": "rejected",
        },
    )
    res = client.get("/runs/fake-0001/feedback")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert "weak" in body and "directions" in body and "forbidden" in body
    assert "text" in body
    lessons = load_lessons(path)
    assert body["text"] == render(feedback_from(lessons))


def test_feedback_text_matches_render(client: TestClient, runs_dir: Path):
    from harness.feedback import write_lesson, feedback_from, load_lessons, render

    path = runs_dir / "fake-0001" / "lessons.jsonl"
    write_lesson(
        path,
        {
            "round": 0,
            "node": 0,
            "family": "features/x",
            "pattern": "seed-x",
            "defect": "crash",
            "delta": 0,
            "verdict": "rejected",
        },
    )
    res = client.get("/runs/fake-0001/feedback")
    text = res.json()["text"]
    expected = render(feedback_from(load_lessons(path)))
    assert text == expected


def test_list_runs_carries_liveness_fields(client: TestClient):
    """Fix-list item 9: the run picker labels entries with started time and
    liveness, so /runs must say when a run was last heard from and whether
    it ended honestly (run_ended on the log)."""
    res = client.get("/runs")
    row = res.json()[0]
    # fake-0001 is written instant=True, so it carries a run_ended event.
    assert row["ended"] is True
    # last_signal is the newest stamp across events and heartbeats — at
    # least as new as the run's start.
    assert row["last_signal"] >= row["started"]


# --- Vercel adapter: an ended run's stream must terminate, not tail -----


def _drain(response) -> list[dict]:
    """Consume a StreamingResponse's SSE frames until the stream closes."""

    async def _consume() -> list[dict]:
        got: list[dict] = []
        async for chunk in response.body_iterator:
            text = chunk.decode("utf-8")
            assert text.startswith("data: ")
            assert text.endswith("\n\n")
            got.append(json.loads(text[len("data: ") :].strip()))
        return got

    return asyncio.run(asyncio.wait_for(_consume(), timeout=3.0))


def _mock_request() -> AsyncMock:
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=False)
    return request


def test_ended_run_event_stream_terminates(client: TestClient, runs_dir: Path):
    """fake-0001 carries run_ended, so the SSE stream must replay every
    event that exists and then CLOSE instead of tailing forever (the
    serverless snapshot viewer would otherwise hang until timeout)."""
    from app.server import get_events

    res = get_events("fake-0001", since=0, stream=True, request=_mock_request())
    got = _drain(res)  # hangs (TimeoutError) if the stream tails forever
    on_disk = [
        json.loads(line)
        for line in (runs_dir / "fake-0001" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert got == on_disk
    assert any(ev.get("type") == "run_ended" for ev in got)


def test_ended_run_heartbeat_stream_terminates(client: TestClient, runs_dir: Path):
    """The heartbeat stream keys off the same run_ended fact on the
    events log — an ended run's heartbeat stream closes too."""
    from app.server import get_heartbeat

    res = get_heartbeat("fake-0001", since=0, stream=True, request=_mock_request())
    _drain(res)  # terminating at all is the assertion


def test_snapshot_host_stream_terminates_without_run_ended(
    client: TestClient, runs_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """On a serverless host (VERCEL env set) no run is ever live: even a
    record with no run_ended (a crashed run) replays and closes."""
    monkeypatch.setenv("VERCEL", "1")
    path = runs_dir / "fake-0001" / "events.jsonl"
    kept = [
        line
        for line in path.read_text().splitlines()
        if line.strip() and json.loads(line).get("type") != "run_ended"
    ]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    from app.server import get_events

    res = get_events("fake-0001", since=0, stream=True, request=_mock_request())
    got = _drain(res)
    assert len(got) == len(kept)
    assert not any(ev.get("type") == "run_ended" for ev in got)


def test_live_run_stream_still_tails(client: TestClient, runs_dir: Path):
    """Locally (no VERCEL env), a run without run_ended keeps tailing —
    the stream must NOT close after replay."""
    path = runs_dir / "fake-0001" / "events.jsonl"
    kept = [
        line
        for line in path.read_text().splitlines()
        if line.strip() and json.loads(line).get("type") != "run_ended"
    ]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    from app.server import get_events

    res = get_events("fake-0001", since=0, stream=True, request=_mock_request())

    async def _expect_open() -> None:
        count = 0
        with pytest.raises(asyncio.TimeoutError):

            async def _consume() -> None:
                nonlocal count
                async for _ in res.body_iterator:
                    count += 1

            await asyncio.wait_for(_consume(), timeout=1.5)
        assert count == len(kept)  # replayed everything, then stayed open

    asyncio.run(_expect_open())
