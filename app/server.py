"""Phase 2: FastAPI SSE server over events.jsonl / heartbeat.jsonl."""

from __future__ import annotations


def list_runs() -> list[dict]:
    raise NotImplementedError


def get_events(run_id: str, since: int = 0, stream: bool = True):
    raise NotImplementedError


def get_heartbeat(run_id: str, since: int = 0, stream: bool = True):
    raise NotImplementedError
