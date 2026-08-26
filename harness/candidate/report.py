"""Phase 3: candidate-side progress/result/checkpoint writers (stdlib only)."""

from __future__ import annotations

from pathlib import Path


def progress(step: int, total: int, loss: float) -> None:
    raise NotImplementedError


def result(metrics: dict, preds_path: Path | str) -> None:
    raise NotImplementedError


class checkpoint:
    @staticmethod
    def save(state) -> Path:
        raise NotImplementedError
