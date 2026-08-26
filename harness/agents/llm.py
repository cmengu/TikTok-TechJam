"""Phase 7: LLM adapters and usage logging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Usage:
    tokens_in: int
    tokens_out: int


class LLM(Protocol):
    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        ...


class FakeLLM:
    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        raise NotImplementedError


class AnthropicLLM:
    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        raise NotImplementedError


class OpenAILLM:
    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        raise NotImplementedError


def log_usage(events, node, slice: str, usage: Usage) -> None:
    raise NotImplementedError
