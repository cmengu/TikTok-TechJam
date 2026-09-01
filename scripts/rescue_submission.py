"""Write a submission for a finished run that never promoted a node.

The loop only writes submission/ on a promotion (tree.py, the promoted
branch). A run where nothing beats the baseline therefore ends with no
submittable artefact at all — even though the rules ask for the
validation-best candidate, which in that case simply IS the baseline.

This re-runs one node's candidate on the submission features and writes
runs/<run-id>/submission/, exactly as a promotion would have. It reads
the run's own event log to pick the node; it never invents a score.

    python scripts/rescue_submission.py <run-id>              # best node, else baseline
    python scripts/rescue_submission.py <run-id> --node 4     # a specific attempt
    python scripts/rescue_submission.py <run-id> --node baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from harness.events import EventLog  # noqa: E402
from harness.outputs import write_submission  # noqa: E402
from harness.protocol import load as load_protocol  # noqa: E402
from harness.runner import Runner  # noqa: E402
from harness.tasks import make_task  # noqa: E402
from harness.tree import Workspace  # noqa: E402
from harness.types import Cost, Node  # noqa: E402


def read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def best_node(events: list[dict]) -> tuple[int | None, float | None]:
    """Highest mean primary score across verdicts — the run's own record."""
    best_id, best_score = None, None
    for ev in events:
        if ev.get("type") != "verdict" or ev.get("metric") != "primary":
            continue
        scores = [s for s in (ev.get("scores") or []) if isinstance(s, (int, float))]
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        if best_score is None or mean > best_score:
            best_id, best_score = ev.get("node"), mean
    return best_id, best_score


def node_commit(events: list[dict], node_id: int) -> str | None:
    for ev in events:
        if ev.get("node") == node_id and ev.get("commit"):
            return str(ev["commit"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--node", default="best", help="'best' (default), 'baseline', or an attempt id")
    ap.add_argument("--protocol", default="protocols/kuairand.yaml")
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    run_dir = REPO / "runs" / args.run_id
    if not run_dir.is_dir():
        print(f"no such run: {run_dir}", file=sys.stderr)
        return 2

    events_raw = read_events(run_dir)
    if args.node == "best":
        node_id, score = best_node(events_raw)
        if node_id is None:
            print("no scored verdict in the log; falling back to baseline")
            node_id = None
        else:
            print(f"best scored attempt: node {node_id} at primary {score:.4f}")
    elif args.node == "baseline":
        node_id = None
    else:
        node_id = int(args.node)

    protocol = load_protocol(Path(args.protocol))
    task = make_task(protocol, n_impressions=args.rows)
    paths = task.prepare(protocol, run_dir / "data")
    events = EventLog(run_dir, args.run_id, protocol)

    run_cfg = {
        "paths": paths,
        "run_dir": run_dir,
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "emb": 16,
        "dropout": 0.0,
        "epochs": 12,
        "features": "base",
        "poll_s": 0.5,
        "timeout_s": 600.0,
        "stall_threshold_s": 300.0,
    }
    runner = Runner(events, task, run_cfg, heartbeat_s=30.0)
    workspace = Workspace(run_dir, args.run_id, candidate_dir=task.candidate_dir)

    # Candidate source: the pristine template for the baseline, or the node's
    # committed workspace tree for a specific attempt.
    candidate_src = Path(task.candidate_dir)
    if node_id is not None:
        commit = node_commit(events_raw, node_id)
        if commit:
            workspace.checkout(commit)
            candidate_src = Path(workspace.path)
            print(f"checked out node {node_id} at {commit[:8]}")
        else:
            print(f"node {node_id} has no commit in the log; using the baseline template")
            node_id = None

    node = Node(
        id=node_id if node_id is not None else 1,
        parent=None,
        hypothesis_id="rescue",
        commit=None,
        state="promoted",
        rung="full",
        kind="improve",
        scores={},
        seeds=[],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=0,
    )

    run_env = runner._build_env(
        Path(workspace.path), paths, args.seed, "full", {}, 12, None
    )
    dest = write_submission(
        node,
        task,
        protocol,
        "predictions",
        run_dir,
        events=events,
        seed=args.seed,
        candidate_src=candidate_src,
        run_env=run_env,
    )
    print(f"submission written: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
