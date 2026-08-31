"""Phase 2: FastAPI SSE server over events.jsonl / heartbeat.jsonl."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI()


def _run_dir(run_id: str) -> Path:
    path = RUNS / run_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def list_runs() -> list[dict]:
    """Return [{run_id, task, protocol_hash, started}] from each run's first event."""
    if not RUNS.is_dir():
        return []
    rows: list[dict] = []
    for child in sorted(RUNS.iterdir()):
        if not child.is_dir():
            continue
        events = child / "events.jsonl"
        if not events.is_file():
            continue
        lines = _read_jsonl(events)
        if not lines:
            continue
        first = lines[0]
        protocol = first.get("protocol") or {}
        rows.append(
            {
                "run_id": child.name,
                "task": protocol.get("task") or first.get("run"),
                "protocol_hash": first.get("protocol_hash"),
                "started": first.get("t"),
            }
        )
    rows.sort(key=lambda r: r.get("started") or "", reverse=True)
    return rows


async def _sse_tail(
    path: Path, since: int, request: Request
) -> AsyncIterator[bytes]:
    """Replay lines with seq>since, then poll for new lines every 0.5s."""
    offset = 0
    while True:
        if await request.is_disconnected():
            return
        if path.is_file():
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(offset)
                chunk = fh.read()
                offset = fh.tell()
            if chunk:
                for line in chunk.splitlines():
                    if not line.strip():
                        continue
                    ev = json.loads(line)
                    if ev.get("seq", 0) > since:
                        since = ev["seq"]
                        payload = json.dumps(
                            ev, separators=(",", ":"), ensure_ascii=False
                        )
                        yield f"data: {payload}\n\n".encode("utf-8")
        await asyncio.sleep(0.5)


def _json_since(path: Path, since: int) -> list[dict]:
    return [ev for ev in _read_jsonl(path) if ev.get("seq", 0) > since]


def get_events(
    run_id: str, since: int = 0, stream: bool = True, request: Request | None = None
):
    path = _run_dir(run_id) / "events.jsonl"
    if stream:
        if request is None:
            raise ValueError("request required for streaming")
        return StreamingResponse(
            _sse_tail(path, since, request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    return JSONResponse(_json_since(path, since))


def get_heartbeat(
    run_id: str, since: int = 0, stream: bool = True, request: Request | None = None
):
    path = _run_dir(run_id) / "heartbeat.jsonl"
    if stream:
        if request is None:
            raise ValueError("request required for streaming")
        return StreamingResponse(
            _sse_tail(path, since, request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    return JSONResponse(_json_since(path, since))


@app.get("/runs")
def api_list_runs():
    return list_runs()


@app.get("/runs/{run_id}/events")
async def api_get_events(
    request: Request,
    run_id: str,
    since: int = Query(0),
    stream: bool = Query(True),
):
    return get_events(run_id, since=since, stream=stream, request=request)


@app.get("/runs/{run_id}/heartbeat")
async def api_get_heartbeat(
    request: Request,
    run_id: str,
    since: int = Query(0),
    stream: bool = Query(True),
):
    return get_heartbeat(run_id, since=since, stream=stream, request=request)


@app.get("/runs/{run_id}/audit/replication")
def api_audit_replication(run_id: str):
    from harness.audit import replication_pairs

    events = _read_jsonl(_run_dir(run_id) / "events.jsonl")
    return replication_pairs(events)


@app.get("/runs/{run_id}/audit/cost")
def api_audit_cost(run_id: str):
    from harness.audit import cost_by_slice

    events = _read_jsonl(_run_dir(run_id) / "events.jsonl")
    return cost_by_slice(events)


@app.get("/runs/{run_id}/audit/reliability")
def api_audit_reliability(run_id: str):
    from harness.audit import reliability

    events = _read_jsonl(_run_dir(run_id) / "events.jsonl")
    return reliability(events)


@app.get("/runs/{run_id}/audit/monitors")
def api_audit_monitors(run_id: str):
    events = _read_jsonl(_run_dir(run_id) / "events.jsonl")
    try:
        from harness.overfit import (
            gap_alarm,
            headline,
            ladder_queries,
            oracle_gap,
            seed_consistency_by_node,
            split_rank_corr,
        )
        from harness.outputs import claim_level, claim_reason
    except ImportError:
        return {"available": False, "reason": "harness.overfit not present"}

    primary, spread = headline(events)
    return {
        "available": True,
        "primary": primary,
        "spread": spread,
        "oracle_gap": oracle_gap(events),
        "gap_alarm": gap_alarm(events),
        "seed_consistency": seed_consistency_by_node(events),
        "rank_corr": split_rank_corr(events),
        "ladder_queries": ladder_queries(events),
        "claim_level": claim_level(events),
        "claim_reason": claim_reason(events),
    }


@app.get("/")
def index():
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store"},
    )


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def serve() -> None:
    """Run the dev server. Import string, not the object, so reload works."""
    import uvicorn

    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    serve()
