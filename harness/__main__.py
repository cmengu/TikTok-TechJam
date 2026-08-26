"""CLI dispatcher. Phase 1 wires ``init``; later phases add ``fake``, ``run``, etc."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from harness.events import EventLog
from harness.protocol import load


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "init":
        print("not implemented")
        raise SystemExit(1)
    if len(argv) < 2:
        print("usage: python -m harness init <protocol.yaml>", file=sys.stderr)
        raise SystemExit(2)

    protocol = load(argv[1])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{protocol.task}-{stamp}"
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    log = EventLog(run_dir, run_id, protocol)
    log.close()

    print(f"run_id={run_id}")
    print(f"protocol_hash={protocol.protocol_hash}")


if __name__ == "__main__":
    main(sys.argv[1:])
