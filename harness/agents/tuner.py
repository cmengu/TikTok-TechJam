"""Phase 7: Optuna screen-rung knob tuner."""

from __future__ import annotations

from harness.types import Hypothesis, Node


def tune(node: Node, knob_space, runner, events, budget: int, screen_seed: int) -> list[Hypothesis]:
    raise NotImplementedError
