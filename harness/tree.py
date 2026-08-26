"""Phase 6: run tree, hypothesis queue, workspace, ladder loop."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from harness.events import EventLog
from harness.types import Hypothesis, Node

TRANSITIONS: dict[str, set[str]] = {}  # filled in phase 6
STALL_STEPS = 4
MAX_LIVE_BRANCHES = 3
DEBUG_DEPTH = 3
LESSONS_WINDOW = 30


class IllegalTransition(Exception):
    """Raised when a node state change is not in TRANSITIONS."""


class Coder(Protocol):
    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        ...


class PatchCoder:
    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        raise NotImplementedError


class Workspace:
    def commit_node(self, node_id: int, diff_path: Path) -> str:
        raise NotImplementedError

    def checkout(self, commit: str) -> None:
        raise NotImplementedError


class Queue:
    def push(self, hyp: Hypothesis) -> bool:
        raise NotImplementedError

    def rerank(self, family_stats: dict) -> list[str]:
        raise NotImplementedError

    def pop(self) -> Hypothesis:
        raise NotImplementedError


def family_stats(events: list[dict]) -> dict[str, dict]:
    raise NotImplementedError


class Tree:
    def __init__(
        self,
        events: EventLog,
        protocol,
        task,
        runner,
        measure,
        coder,
        queue: Queue,
        max_nodes: int,
        budget,
    ) -> None:
        raise NotImplementedError

    def step(self) -> bool:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError
