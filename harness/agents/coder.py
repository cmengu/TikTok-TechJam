"""Phase 7: LLM coder that materialises a unified diff."""

from __future__ import annotations

from pathlib import Path

from harness.types import Hypothesis, Node


class LLMCoder:
    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        raise NotImplementedError
