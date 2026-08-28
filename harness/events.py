"""Phase 1: single-writer event log and node-id allocator."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.protocol import Protocol
from harness.types import EVENT_TYPES, STATES

_FSYNC_TYPES = frozenset({"verdict", "submission_written", "run_ended"})
_JSON_DUMP_KW = {
    "separators": (",", ":"),
    "sort_keys": False,
    "ensure_ascii": False,
    "default": str,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class EventLog:
    def __init__(self, run_dir: Path, run_id: str, protocol: Protocol) -> None:
        """Open events.jsonl and heartbeat.jsonl; first line is run_started."""
        self._run_dir = Path(run_dir)
        self._run_id = run_id
        self._protocol = protocol
        self._run_dir.mkdir(parents=True, exist_ok=True)

        self._events_path = self._run_dir / "events.jsonl"
        self._heartbeat_path = self._run_dir / "heartbeat.jsonl"
        self._events_file = self._events_path.open("a", encoding="utf-8")
        self._heartbeat_file = self._heartbeat_path.open("a", encoding="utf-8")

        self._queue: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
        self._closed = False
        self._close_lock = threading.Lock()

        self._seq_lock = threading.Lock()
        self._event_seq = 0
        self._heartbeat_seq = 0

        self._node_lock = threading.Lock()
        self._next_node = 1

        self._writer = threading.Thread(target=self._writer_loop, name="eventlog-writer", daemon=True)
        self._writer.start()

        self.emit(
            "run_started",
            summary=f"run {run_id} started",
            protocol={
                "schema_version": protocol.schema_version,
                "task": protocol.task,
                "ruler": protocol.ruler,
                "run": protocol.run,
                "protocol_hash": protocol.protocol_hash,
                "protocol_path": str(protocol.path),
            },
        )

    def emit(self, type: str, **fields: Any) -> int:
        """Validate type/state, require summary, stamp seq/t/run/hash; return seq."""
        if type == "heartbeat":
            raise ValueError("heartbeat must use EventLog.heartbeat(), not emit()")
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type!r}")
        if "summary" not in fields or not isinstance(fields["summary"], str):
            raise ValueError("summary is required and must be a str")
        state = fields.get("state")
        if state is not None and state not in STATES:
            raise ValueError(f"unknown state: {state!r}")

        with self._close_lock:
            if self._closed:
                raise RuntimeError("EventLog is closed")
            with self._seq_lock:
                self._event_seq += 1
                seq = self._event_seq
            event = {
                "schema_version": 1,
                "seq": seq,
                "t": _utc_now_iso(),
                "run": self._run_id,
                "protocol_hash": self._protocol.protocol_hash,
                "type": type,
                **fields,
            }
            self._queue.put(("events", event))
            return seq

    def new_node(self, parent: int | None) -> int:
        """Allocate a node id under a lock."""
        del parent  # reserved for callers; allocator is a single counter
        with self._node_lock:
            node_id = self._next_node
            self._next_node += 1
            return node_id

    def heartbeat(self, worker: str, **fields: Any) -> None:
        """Write to heartbeat.jsonl through the same queue."""
        with self._close_lock:
            if self._closed:
                raise RuntimeError("EventLog is closed")
            with self._seq_lock:
                self._heartbeat_seq += 1
                seq = self._heartbeat_seq
            event = {
                "schema_version": 1,
                "seq": seq,
                "t": _utc_now_iso(),
                "run": self._run_id,
                "protocol_hash": self._protocol.protocol_hash,
                "type": "heartbeat",
                "worker": worker,
                **fields,
            }
            self._queue.put(("heartbeat", event))

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def drain(self) -> None:
        """Block until queued events are written to events.jsonl."""
        while not self._queue.empty():
            time.sleep(0.001)
        if not self._closed:
            self._events_file.flush()

    def close(self) -> None:
        """Drain, fsync, join writer; emit after close raises."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self._queue.put(None)
        self._writer.join()
        for fh in (self._events_file, self._heartbeat_file):
            fh.flush()
            os.fsync(fh.fileno())
            fh.close()

    def _writer_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            kind, event = item
            line = json.dumps(event, **_JSON_DUMP_KW) + "\n"
            if kind == "heartbeat":
                fh = self._heartbeat_file
            else:
                fh = self._events_file
            fh.write(line)
            fh.flush()
            if event.get("type") in _FSYNC_TYPES:
                os.fsync(fh.fileno())
