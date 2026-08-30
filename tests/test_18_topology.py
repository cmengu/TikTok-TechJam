"""Step 11: move policy is a pure fold; the run loop does not decide."""

from __future__ import annotations

import json
from pathlib import Path

from harness.tree import (
    DEBUG_DEPTH,
    MAX_LIVE_BRANCHES,
    Move,
    select,
)
from harness.types import Cost, Node

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fake-events.jsonl"


def _node(
    nid: int,
    *,
    state: str = "screening",
    kind: str = "draft",
    parent: int | None = None,
    scores: dict | None = None,
) -> Node:
    return Node(
        id=nid,
        parent=parent,
        hypothesis_id=f"h-{nid}",
        commit=None,
        state=state,  # type: ignore[arg-type]
        rung="screen",
        kind=kind,  # type: ignore[arg-type]
        scores=scores or {},
        seeds=[],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=nid,
    )


def test_select_drafts_until_min():
    nodes = [_node(1, state="inconclusive", kind="draft")]
    move = select(nodes, 100.0)
    assert move == Move("draft", None, "breadth floor")
    promoted = [
        _node(1, state="promoted", kind="draft"),
        _node(2, state="promoted", kind="draft"),
    ]
    assert select(promoted, 100.0).kind == "draft"
    three = promoted + [_node(3, state="promoted", kind="draft")]
    assert select(three, 100.0).kind != "draft" or select(three, 100.0).reason != "breadth floor"


def test_select_repairs_before_extending():
    nodes = [
        _node(1, state="promoted", kind="draft", scores={"primary": [0.6]}),
        _node(2, state="promoted", kind="draft", scores={"primary": [0.61]}),
        _node(3, state="promoted", kind="draft", scores={"primary": [0.62]}),
        _node(4, state="failed", kind="improve", parent=1),
    ]
    move = select(nodes, 100.0)
    assert move == Move("debug", 4, "repair before extend")


def test_debug_depth_is_capped():
    ancestors = [
        _node(i, state="retired", kind="debug", parent=None if i == 1 else i - 1)
        for i in range(1, DEBUG_DEPTH + 1)
    ]
    tip = _node(DEBUG_DEPTH + 1, state="failed", kind="debug", parent=DEBUG_DEPTH)
    nodes = [
        _node(10, state="promoted", kind="draft", scores={"primary": [0.5]}),
        _node(11, state="promoted", kind="draft", scores={"primary": [0.5]}),
        _node(12, state="promoted", kind="draft", scores={"primary": [0.51]}),
        *ancestors,
        tip,
    ]
    move = select(nodes, 100.0)
    assert move.kind == "improve"
    assert move.reason == "extend best"


def test_branch_cap_blocks_spawn():
    live = [
        _node(1, state="running", kind="draft"),
        _node(2, state="running", kind="improve"),
        _node(3, state="replicating", kind="draft"),
    ]
    assert len(live) == MAX_LIVE_BRANCHES
    move = select(live, 100.0)
    assert move == Move(None, None, "at branch cap")


def test_select_is_a_fold():
    nodes = [
        _node(1, state="promoted", kind="draft", scores={"primary": [0.5]}),
        _node(2, state="failed", kind="improve", parent=1),
        _node(3, state="promoted", kind="draft", scores={"primary": [0.4]}),
        _node(4, state="promoted", kind="draft", scores={"primary": [0.45]}),
    ]
    a = select(nodes, 50.0)
    b = select(nodes, 50.0)
    assert a == b
    assert (a.kind, a.parent, a.reason) == (b.kind, b.parent, b.reason)


def test_replay_fake_log_matches_move_sequence():
    events = [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    recorded = [
        (e.get("kind"), e.get("parent"), e.get("reason"))
        for e in events
        if e.get("type") == "move_selected"
    ]
    assert recorded, "fixture must carry move_selected events"
    replayed: list[tuple] = []
    nodes: list[Node] = []
    by_id: dict[int, Node] = {}
    for e in events:
        if e.get("type") == "move_selected":
            move = select(list(by_id.values()), 100.0)
            replayed.append((move.kind, move.parent, move.reason))
        elif e.get("type") == "node_created":
            node = _node(
                int(e["id"]),
                kind=str(e.get("kind") or "draft"),
                parent=e.get("parent"),
            )
            by_id[node.id] = node
            nodes.append(node)
        elif e.get("type") == "state_changed":
            nid = int(e["node"])
            if nid in by_id:
                by_id[nid].state = e["state"]  # type: ignore[assignment]
    assert replayed == recorded
