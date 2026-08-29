"""Phase 6 slow loop: real runner + real measure, ~200K synthetic, hand hyps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.measure import Measure
from harness.runner import Runner
from harness.tasks.synthetic import SyntheticTask
from harness.tree import PatchCoder, Queue, Tree, Workspace
from harness.types import Cost, Hypothesis, Node

ROOT = Path(__file__).resolve().parents[1]


def _read_events(run_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_hand() -> list[Hypothesis]:
    raw = yaml.safe_load((ROOT / "hypotheses" / "hand.yaml").read_text()) or []
    out: list[Hypothesis] = []
    for row in raw:
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
                patch=ROOT / row["patch"] if row.get("patch") else None,
            )
        )
    return out


@pytest.fixture(scope="module")
def loop_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p6loop")
    proto = placeholder_protocol(tmp)
    run_dir = tmp / "run"
    run_dir.mkdir()
    task = SyntheticTask(n_impressions=200_000)
    paths = task.prepare(proto, run_dir / "data")
    events = EventLog(run_dir, "p6-loop", proto)
    run_cfg = {
        "paths": paths,
        "run_dir": run_dir,
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 12,
        "features": "base",
        "poll_s": 0.5,
        "timeout_s": 600.0,
        "stall_threshold_s": 300.0,
    }
    runner = Runner(events, task, run_cfg, heartbeat_s=30.0)
    measure = Measure(events, proto, band=None)
    workspace = Workspace(run_dir, "p6-loop")
    hyps = _load_hand()
    by_id = {h.id: h for h in hyps}
    queue = Queue(events)
    for h in hyps:
        queue.push(h)
    tree = Tree(
        events,
        proto,
        task,
        runner,
        measure,
        PatchCoder(),
        queue,
        max_nodes=12,
        budget=None,
        workspace=workspace,
        hyp_index=by_id,
        smoke_timeout_s=120.0,
        screen_timeout_s=600.0,
        full_timeout_s=600.0,
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
        summary="baseline calibrate node",
    )
    tree.calibrate_baseline(baseline)
    tree.run()
    events.close()
    return run_dir, tree


@pytest.mark.slow
def test_incumbent_is_f_true(loop_run):
    run_dir, tree = loop_run
    rows = _read_events(run_dir)
    ended = [e for e in rows if e["type"] == "run_ended"]
    assert ended
    inc_id = ended[-1].get("incumbent")
    assert inc_id is not None
    inc_node = tree.nodes[int(inc_id)]
    assert inc_node.hypothesis_id == "h-f-true"

    by_hyp = {n.hypothesis_id: n for n in tree.nodes.values()}
    assert by_hyp["h-f-leak"].state == "leaked"
    assert by_hyp["h-f-zero"].state != "promoted"
    assert by_hyp["h-f-marginal"].state != "rejected"


@pytest.mark.slow
def test_holdout_visits_le_two(loop_run):
    run_dir, _tree = loop_run
    rows = _read_events(run_dir)
    visits = [
        e
        for e in rows
        if e["type"] == "measurement" and e.get("rung") == "holdout"
    ]
    assert len(visits) <= 2


@pytest.mark.slow
def test_run_completes_unattended(loop_run):
    run_dir, _tree = loop_run
    rows = _read_events(run_dir)
    assert not any(e["type"] == "intervention" for e in rows)
    assert any(e["type"] == "run_ended" for e in rows)
