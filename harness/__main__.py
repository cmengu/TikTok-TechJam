"""CLI dispatcher. Phase 1 wires ``init``; phase 2 adds ``fake``."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness.events import EventLog
from harness.fake_run import write as write_fake
from harness.protocol import load


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m harness {init,fake} ...", file=sys.stderr)
        raise SystemExit(2)

    cmd = argv[0]
    if cmd == "init":
        _cmd_init(argv[1:])
    elif cmd == "fake":
        _cmd_fake(argv[1:])
    else:
        print("not implemented")
        raise SystemExit(1)


def _cmd_init(argv: list[str]) -> None:
    if len(argv) < 1:
        print("usage: python -m harness init <protocol.yaml>", file=sys.stderr)
        raise SystemExit(2)

    protocol = load(argv[0])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{protocol.task}-{stamp}"
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    log = EventLog(run_dir, run_id, protocol)
    log.close()

    print(f"run_id={run_id}")
    print(f"protocol_hash={protocol.protocol_hash}")


def _cmd_fake(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m harness fake")
    parser.add_argument("--instant", action="store_true")
    parser.add_argument("--speed", type=float, default=20.0)
    parser.add_argument("--run-id", default="fake-0001")
    args = parser.parse_args(argv)

    run_dir = Path("runs") / args.run_id
    run_id = write_fake(run_dir, speed=args.speed, instant=args.instant)
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main(sys.argv[1:])
