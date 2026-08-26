"""Phase 1: single-writer event log and node-id allocator."""

from __future__ import annotations

from pathlib import Path

from harness.protocol import Protocol


class EventLog:
    def __init__(self, run_dir: Path, run_id: str, protocol: Protocol) -> None:
        """Open events.jsonl and heartbeat.jsonl; first line is run_started."""
        raise NotImplementedError

    def emit(self, type: str, **fields) -> int:
        """Validate type/state, require summary, stamp seq/t/run/hash; return seq."""
        raise NotImplementedError

    def new_node(self, parent: int | None) -> int:
        """Allocate a node id under a lock."""
        raise NotImplementedError

    def heartbeat(self, worker: str, **fields) -> None:
        """Write to heartbeat.jsonl through the same queue."""
        raise NotImplementedError

    def close(self) -> None:
        """Drain, fsync, join writer; emit after close raises."""
        raise NotImplementedError
