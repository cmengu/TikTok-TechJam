"""Shared helpers for agent modules."""

from __future__ import annotations

from harness.types import Cost


def cost_dict(cost: Cost) -> dict:
    return {
        "gpu_s": cost.gpu_s,
        "tokens_in": cost.tokens_in,
        "tokens_out": cost.tokens_out,
        "slice": cost.slice,
    }
