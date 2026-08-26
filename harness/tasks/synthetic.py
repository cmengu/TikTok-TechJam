"""Phase 3: synthetic funnel benchmark with planted effects."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from harness.protocol import Protocol
from harness.tasks.base import TaskPaths

FAILURE_ENV = "SYNTHETIC_FAIL"


def generate(
    seed: int,
    n_users: int = 20_000,
    n_items: int = 2_000,
    n_impressions: int = 1_000_000,
):
    raise NotImplementedError


class SyntheticTask:
    name = "synthetic"

    def prepare(self, protocol: Protocol, root: Path) -> TaskPaths:
        raise NotImplementedError

    def candidate_env(self, paths: TaskPaths) -> dict:
        raise NotImplementedError

    def score(
        self, preds_path: Path, split: Literal["search", "holdout"]
    ) -> dict[str, float]:
        raise NotImplementedError

    def rows(self, split: str) -> int:
        raise NotImplementedError
