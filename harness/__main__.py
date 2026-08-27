"""CLI dispatcher. Phase 1 wires ``init``; phase 2 adds ``fake``; phase 4 adds ``run-one``."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness.events import EventLog
from harness.fake_run import write as write_fake
from harness.protocol import Protocol, load, protocol_hash


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m harness {init,fake,run-one} ...", file=sys.stderr)
        raise SystemExit(2)

    cmd = argv[0]
    if cmd == "init":
        _cmd_init(argv[1:])
    elif cmd == "fake":
        _cmd_fake(argv[1:])
    elif cmd == "run-one":
        _cmd_run_one(argv[1:])
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


def _cmd_run_one(argv: list[str]) -> None:
    """Phase 4 gate: one real node through a real EventLog, watched in the app."""
    import copy

    from harness.runner import Runner
    from harness.tasks.synthetic import SyntheticTask
    from harness.types import Cost, Node

    parser = argparse.ArgumentParser(prog="python -m harness run-one")
    parser.add_argument("--protocol", default="protocols/synthetic.yaml")
    parser.add_argument("--fail", default=None,
                        help="SYNTHETIC_FAIL mode: crash|oom_cuda|oom_host|nan|hang|no_result|bad_schema")
    parser.add_argument("--rows", type=int, default=50_000,
                        help="synthetic impressions; anything but 1000000 uses placeholder hashes")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--heartbeat", type=float, default=2.0)
    args = parser.parse_args(argv)

    protocol = load(args.protocol)
    if args.rows != 1_000_000:
        # A smaller dataset cannot match the frozen sha256 fields; run under a
        # demo protocol whose hash fields are placeholders (prepare() skips them).
        ruler = copy.deepcopy(protocol.ruler)
        ruler["data"]["train"]["sha256"] = "0" * 63 + "1"
        ruler["data"]["test"]["sha256"] = "0" * 63 + "2"
        ruler["splits"]["search_validation"]["sha256"] = "0" * 63 + "3"
        ruler["splits"]["holdout_validation"]["sha256"] = "0" * 63 + "4"
        ruler["scoring"]["script_sha"] = "0" * 63 + "5"
        protocol = Protocol(
            task=protocol.task, schema_version=protocol.schema_version, ruler=ruler,
            run=protocol.run, protocol_hash=protocol_hash(ruler), path=protocol.path,
        )
        print(f"note: rows={args.rows} -> demo protocol with placeholder hashes", file=sys.stderr)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{protocol.task}-{stamp}"
    run_dir = (Path("runs") / run_id).resolve()  # child runs with cwd=workspace
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"run_id={run_id}", flush=True)

    task = SyntheticTask(n_impressions=args.rows)
    paths = task.prepare(protocol, run_dir / "data")
    events = EventLog(run_dir, run_id, protocol)
    try:
        run_cfg = {
            "paths": paths, "run_dir": run_dir, "device": "cpu",
            "batch": 2048, "lr": "1e-3", "epochs": 1, "features": "base", "poll_s": 0.5,
        }
        runner = Runner(events, task, run_cfg, heartbeat_s=args.heartbeat)
        node = Node(
            id=1, parent=None, hypothesis_id="h-base", commit=None, state="running",
            rung="screen", kind="draft", scores={}, seeds=[args.seed],
            cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"), created_seq=1,
        )
        overrides = {"SYNTHETIC_FAIL": args.fail} if args.fail else {}
        result = runner.run(node, "screen", args.seed, args.timeout, env_overrides=overrides)
    finally:
        events.close()

    print(f"ok={result.ok} failure_class={result.failure_class} metrics={result.metrics}")
    if result.stderr_tail:
        print("stderr_tail:", result.stderr_tail.strip().splitlines()[-1][:200])
    print(f"events: {run_dir / 'events.jsonl'}")


if __name__ == "__main__":
    main(sys.argv[1:])
