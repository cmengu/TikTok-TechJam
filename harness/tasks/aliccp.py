"""Phase 8: Ali-CCP task adapter over partitioned parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from harness.protocol import Protocol
from harness.tasks.base import TaskPaths


class AliCCPTask:
    name = "aliccp"

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
