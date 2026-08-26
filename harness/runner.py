"""Phase 4: spawn candidate, timeout, classify failure, recover."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from harness.events import EventLog
from harness.tasks.base import Task
from harness.types import Node, Rung, RunResult

FAILURE_CLASSES = (
    "cuda_oom",
    "host_oom",
    "diverged",
    "timeout",
    "contract_violation",
    "crash",
)

RECOVERY: dict = {}  # filled in phase 4


@dataclass
class Completed:
    returncode: int
    stderr_tail: str
    wall_s: float


class Backend(Protocol):
    def run(
        self,
        workspace: Path,
        cmd: list[str],
        env: dict,
        timeout_s: float,
        on_progress: Callable[[dict], None],
    ) -> Completed:
        ...


class LocalBackend:
    def run(
        self,
        workspace: Path,
        cmd: list[str],
        env: dict,
        timeout_s: float,
        on_progress: Callable[[dict], None],
    ) -> Completed:
        raise NotImplementedError


def derived_timeout(
    seconds_per_row_screen: float,
    rows: int,
    epochs: int,
    safety: float = 2.0,
    floor_s: float = 60,
) -> float:
    raise NotImplementedError


def classify(
    returncode: int,
    stderr_tail: str,
    progress: list[dict],
    result_path: Path | None,
) -> str | None:
    raise NotImplementedError


class Runner:
    def __init__(
        self,
        events: EventLog,
        task: Task,
        run_cfg: dict,
        backend: Backend = None,  # type: ignore[assignment]
        heartbeat_s: float = 30.0,
    ) -> None:
        raise NotImplementedError

    def run(
        self,
        node: Node,
        rung: Rung,
        seed: int,
        timeout_s: float,
        env_overrides: dict = None,  # type: ignore[assignment]
        attempt: int = 1,
    ) -> RunResult:
        raise NotImplementedError
