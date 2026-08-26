"""Phase 3: Task adapter interface shared by synthetic and Ali-CCP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from harness.protocol import Protocol as HarnessProtocol


@dataclass
class TaskPaths:
    train: Path
    search_validation: Path
    holdout_validation: Path
    scoring_script: Path | None


class Task(Protocol):
    name: str

    def prepare(self, protocol: HarnessProtocol, root: Path) -> TaskPaths:
        ...

    def candidate_env(self, paths: TaskPaths) -> dict:
        ...

    def score(
        self, preds_path: Path, split: Literal["search", "holdout"]
    ) -> dict[str, float]:
        ...

    def rows(self, split: str) -> int:
        ...
