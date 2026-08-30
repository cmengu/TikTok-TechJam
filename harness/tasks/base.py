"""Task adapter interface shared by synthetic and KuaiRand."""

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
    metric: str
    prediction_columns: tuple[str, ...]
    include_oracle_delta: bool
    candidate_dir: Path

    def prepare(self, protocol: HarnessProtocol, root: Path) -> TaskPaths:
        ...

    def candidate_env(self, paths: TaskPaths, *, rung: str = "screen") -> dict:
        ...

    def score(
        self, preds_path: Path, split: Literal["search", "holdout"]
    ) -> dict[str, float]:
        ...

    def rows(self, split: str) -> int:
        ...

    def submission_features(self) -> Path | None:
        """VALID path for the promotion re-run, or None to copy existing preds."""
        ...

    def readback_submission(self, path: Path) -> dict:
        ...
