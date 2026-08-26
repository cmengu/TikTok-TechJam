"""Phase 9: submission writer, convergence, registry, report."""

from __future__ import annotations

from pathlib import Path
from typing import Literal


def write_submission(
    node,
    task,
    protocol,
    mode: Literal["predictions", "checkpoint"],
    out_dir: Path,
) -> Path:
    raise NotImplementedError


class Convergence:
    def __init__(self, eps: float, n_rounds: int) -> None:
        raise NotImplementedError

    def update(self, searchval_score: float) -> bool:
        raise NotImplementedError


def write_prediction(events, holdout_score: float, band) -> int:
    raise NotImplementedError


def register(run_dir: Path, protocol, status: str, final_scores: dict) -> None:
    raise NotImplementedError


def report(events: list[dict], out_path: Path) -> Path:
    raise NotImplementedError
