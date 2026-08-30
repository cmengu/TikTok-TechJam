"""CLI dispatcher. Phase 1 wires ``init``; phase 2 adds ``fake``; phase 4 adds ``run-one``;
phase 6 adds ``run`` (resume deferred — Tree.rebuild only)."""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harness.events import EventLog
from harness.fake_run import write as write_fake
from harness.protocol import Protocol, load, protocol_hash
from harness.attribute import claim_from_bank_row
from harness.types import Hypothesis

REPO_ROOT = Path(__file__).resolve().parents[1]


def _placeholder_ruler_if_demo(protocol: Protocol, rows: int) -> Protocol:
    """Synthetic demo only: swap ruler digests for placeholders when rows != 1e6."""
    if protocol.task != "synthetic" or rows == 1_000_000:
        return protocol
    ruler = copy.deepcopy(protocol.ruler)
    ruler["data"]["train"]["sha256"] = "0" * 63 + "1"
    ruler["data"]["test"]["sha256"] = "0" * 63 + "2"
    ruler["splits"]["search_validation"]["sha256"] = "0" * 63 + "3"
    ruler["splits"]["holdout_validation"]["sha256"] = "0" * 63 + "4"
    ruler["scoring"]["script_sha"] = "0" * 63 + "5"
    return Protocol(
        task=protocol.task,
        schema_version=protocol.schema_version,
        ruler=ruler,
        run=protocol.run,
        protocol_hash=protocol_hash(ruler),
        path=protocol.path,
    )


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m harness {init,fake,run-one,run} ...", file=sys.stderr)
        raise SystemExit(2)

    cmd = argv[0]
    if cmd == "init":
        _cmd_init(argv[1:])
    elif cmd == "fake":
        _cmd_fake(argv[1:])
    elif cmd == "run-one":
        _cmd_run_one(argv[1:])
    elif cmd == "run":
        _cmd_run(argv[1:])
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


def _load_hypotheses(path: Path) -> list[Hypothesis]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    out: list[Hypothesis] = []
    for row in raw:
        patch = row.get("patch")
        patch_path = None
        if patch:
            patch_path = Path(patch).expanduser()
            if not patch_path.is_absolute():
                patch_path = (REPO_ROOT / patch_path).resolve()
            else:
                patch_path = patch_path.resolve()
        claim = None
        if row.get("observables") or row.get("claim"):
            claim = claim_from_bank_row(row, str(row["mechanism"]))
        out.append(
            Hypothesis(
                id=str(row["id"]),
                stage=row["stage"],
                mechanism=str(row["mechanism"]),
                description=str(row["description"]),
                citation=str(row.get("citation") or "no prior"),
                expected_gain=float(row.get("expected_gain") or 0.0),
                expected_gpu_h=float(row.get("expected_gpu_h") or 0.1),
                parent_node=row.get("parent_node"),
                patch=patch_path,
                pattern=str(row.get("pattern") or row["mechanism"]),
                claim=claim,
            )
        )
    return out


def _cmd_run(argv: list[str]) -> None:
    """Phase 6/7: calibrate → queue hypotheses → Tree.run (no resume verb)."""
    import copy
    import json

    from harness.agents.brief import compose
    from harness.agents.cache import ResearchCache
    from harness.agents.coder import LLMCoder
    from harness.agents.llm import AnthropicLLM
    from harness.agents.researcher import propose
    from harness.measure import Measure
    from harness.runner import Runner
    from harness.tasks import make_task
    from harness.tree import PatchCoder, Queue, Tree, Workspace, family_stats
    from harness.types import Cost, Node

    parser = argparse.ArgumentParser(prog="python -m harness run")
    parser.add_argument("protocol", nargs="?", default="protocols/synthetic.yaml")
    parser.add_argument(
        "--hypotheses",
        default=None,
        help="hand demo yaml; omit for LLM agent path (bank.yaml + propose)",
    )
    parser.add_argument("--max-nodes", type=int, default=20)
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--budget", type=float, default=None, help="GPU-hours cap")
    args = parser.parse_args(argv)

    protocol = _placeholder_ruler_if_demo(load(args.protocol), args.rows)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{protocol.task}-{stamp}"
    run_dir = (Path("runs") / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"run_id={run_id}", flush=True)
    print(
        f"watch: http://127.0.0.1:8000/?run={run_id}  (uvicorn app.server:app)",
        flush=True,
    )

    hyps_path = (
        Path(args.hypotheses)
        if args.hypotheses is not None
        else Path("hypotheses/bank.yaml")
    )
    use_agents = args.hypotheses is None
    hyps = _load_hypotheses(hyps_path)
    task = make_task(protocol, n_impressions=args.rows)
    paths = task.prepare(protocol, run_dir / "data")
    events = EventLog(run_dir, run_id, protocol)
    try:
        run_cfg = {
            "paths": paths,
            "run_dir": run_dir,
            "device": "cpu",
            "batch": 2048,
            "lr": "1e-3",
            "emb": 16,
            "dropout": 0.0,
            "epochs": args.epochs,
            "features": "base",
            "poll_s": 0.5,
            "timeout_s": 600.0,
            "stall_threshold_s": 300.0,
            "brief_path": "context/Backend_plan.md",
            "models": {
                "researcher": "claude-sonnet-5",
                "coder": "claude-haiku-4-5-20251001",
            },
        }
        runner = Runner(events, task, run_cfg, heartbeat_s=30.0)
        measure = Measure(events, protocol, band=None, metric=task.metric)
        workspace = Workspace(run_dir, run_id, candidate_dir=task.candidate_dir)
        queue = Queue(events)
        hyp_index = {h.id: h for h in hyps}
        for h in hyps:
            queue.push(h)

        if use_agents:
            brief_path = Path(run_cfg["brief_path"])
            brief = compose(brief_path, protocol)
            llm = AnthropicLLM(models=run_cfg["models"])
            cache = ResearchCache(protocol.protocol_hash, events=events)
            coder = LLMCoder(llm, workspace, events=events)
            tree_holder: dict[str, Tree] = {}

            def _lessons() -> list[dict]:
                p = run_dir / "lessons.jsonl"
                if not p.is_file():
                    return []
                rows: list[dict] = []
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
                return rows[-30:]

            def refill_queue() -> None:
                tree = tree_holder["tree"]
                inc = tree.incumbent
                inc_summary = (
                    f"node {inc.id} state={inc.state} commit={inc.commit}"
                    if inc is not None
                    else "no incumbent yet"
                )
                cache.node_id = inc.id if inc is not None else None
                stats = family_stats(tree._read_log())  # noqa: SLF001
                hyp = propose(llm, brief, inc_summary, stats, _lessons(), cache)
                if hyp is None:
                    return
                hyp_index[hyp.id] = hyp
                queue.push(hyp)
                queue.rerank(family_stats(tree._read_log()))  # noqa: SLF001

            tree = Tree(
                events,
                protocol,
                task,
                runner,
                measure,
                coder,
                queue,
                max_nodes=args.max_nodes,
                budget=args.budget,
                workspace=workspace,
                hyp_index=hyp_index,
                refill_queue=refill_queue,
            )
            tree_holder["tree"] = tree
        else:
            tree = Tree(
                events,
                protocol,
                task,
                runner,
                measure,
                PatchCoder(),
                queue,
                max_nodes=args.max_nodes,
                budget=args.budget,
                workspace=workspace,
                hyp_index=hyp_index,
            )
        baseline = Node(
            id=events.new_node(None),
            parent=None,
            hypothesis_id="h-base-cal",
            commit=workspace.head(),
            state="promoted",
            rung="full",
            kind="draft",
            scores={},
            seeds=[1, 2, 3],
            cost=Cost(0.0, 0, 0, "training"),
            created_seq=0,
        )
        events.emit(
            "node_created",
            id=baseline.id,
            parent=None,
            kind="draft",
            hypothesis_id=baseline.hypothesis_id,
            summary=f"node {baseline.id} baseline for calibrate",
        )
        tree.calibrate_baseline(baseline)
        tree.run()
    finally:
        events.close()
    print(f"events: {run_dir / 'events.jsonl'}")


def _cmd_run_one(argv: list[str]) -> None:
    """Phase 4 gate: one real node through a real EventLog, watched in the app."""
    import copy

    from harness.runner import Runner
    from harness.tasks import make_task
    from harness.types import Cost, Node

    parser = argparse.ArgumentParser(prog="python -m harness run-one")
    parser.add_argument("--protocol", default="protocols/synthetic.yaml")
    parser.add_argument(
        "--fail",
        default=None,
        help="SYNTHETIC_FAIL mode: crash|oom_cuda|oom_host|nan|hang|no_result|bad_schema",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50_000,
        help="synthetic impressions; anything but 1000000 uses placeholder hashes",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--heartbeat", type=float, default=2.0)
    args = parser.parse_args(argv)

    loaded = load(args.protocol)
    protocol = _placeholder_ruler_if_demo(loaded, args.rows)
    if protocol is not loaded:
        print(
            f"note: rows={args.rows} -> demo protocol with placeholder hashes",
            file=sys.stderr,
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{protocol.task}-{stamp}"
    run_dir = (Path("runs") / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"run_id={run_id}", flush=True)
    print(
        f"watch: http://127.0.0.1:8000/?run={run_id}  (uvicorn app.server:app)",
        flush=True,
    )

    task = make_task(protocol, n_impressions=args.rows)
    paths = task.prepare(protocol, run_dir / "data")
    events = EventLog(run_dir, run_id, protocol)
    try:
        run_cfg = {
            "paths": paths,
            "run_dir": run_dir,
            "device": "cpu",
            "batch": 2048,
            "lr": "1e-3",
            "epochs": 1,
            "features": "base",
            "poll_s": 0.5,
        }
        runner = Runner(events, task, run_cfg, heartbeat_s=args.heartbeat)
        node = Node(
            id=1,
            parent=None,
            hypothesis_id="h-base",
            commit=None,
            state="running",
            rung="screen",
            kind="draft",
            scores={},
            seeds=[args.seed],
            cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"),
            created_seq=1,
        )
        events.emit(
            "node_created",
            id=node.id,
            parent=None,
            kind=node.kind,
            hypothesis_id=node.hypothesis_id,
            summary="node 1 created as draft under root (run-one)",
        )
        overrides = {"SYNTHETIC_FAIL": args.fail} if args.fail else {}
        result = runner.run(
            node, "screen", args.seed, args.timeout, env_overrides=overrides
        )
    finally:
        events.close()

    print(f"ok={result.ok} failure_class={result.failure_class} metrics={result.metrics}")
    if result.stderr_tail:
        print("stderr_tail:", result.stderr_tail.strip().splitlines()[-1][:200])
    print(f"events: {run_dir / 'events.jsonl'}")


if __name__ == "__main__":
    main(sys.argv[1:])
