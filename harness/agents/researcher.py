"""Phase 7: research pass that proposes a schema-validated hypothesis."""

from __future__ import annotations

from harness.types import Hypothesis


def propose(llm, brief: str, incumbent_summary: str, family_stats, lessons: list[dict], cache) -> Hypothesis | None:
    raise NotImplementedError
