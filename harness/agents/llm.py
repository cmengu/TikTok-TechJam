"""Phase 7: LLM adapters and usage logging."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from harness.agents._util import cost_dict
from harness.types import Cost


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
    """Scripted responses per role; raises if exhausted."""

    def __init__(
        self,
        scripts: dict[str, list[tuple[Any, Usage]]] | None = None,
    ) -> None:
        self._scripts: dict[str, list[tuple[Any, Usage]]] = dict(scripts or {})
        self._cursor: dict[str, int] = {}
        self.prompts: dict[str, list[str]] = {}

    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        self.prompts.setdefault(role, []).append(prompt)
        bucket = self._scripts.get(role, [])
        idx = self._cursor.get(role, 0)
        if idx >= len(bucket):
            raise RuntimeError(f"FakeLLM exhausted for role {role!r}")
        self._cursor[role] = idx + 1
        return bucket[idx]


class AnthropicLLM:
    """Thin Anthropic Messages API adapter."""

    def __init__(self, models: dict[str, str] | None = None) -> None:
        self.models = models or {
            "researcher": "claude-sonnet-5",
            "coder": "claude-haiku-4-5-20251001",
        }
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        model = self.models.get(role, self.models.get("researcher", "claude-sonnet-5"))
        system = (
            "Respond with JSON only, no markdown fences."
            if schema is not None
            else "Respond with a unified diff only, no prose."
        )
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        usage_raw = data.get("usage", {})
        usage = Usage(
            tokens_in=int(usage_raw.get("input_tokens", 0)),
            tokens_out=int(usage_raw.get("output_tokens", 0)),
        )
        if schema is not None:
            return json.loads(text.strip()), usage
        return text.strip(), usage


class OpenAILLM:
    """Thin OpenAI chat adapter (not used in the phase-7 gate)."""

    def __init__(self, models: dict[str, str] | None = None) -> None:
        self.models = models or {
            "researcher": "gpt-4.1",
            "coder": "gpt-4.1-mini",
        }
        self._api_key = os.environ.get("OPENAI_API_KEY", "")

    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        model = self.models.get(role, self.models.get("researcher", "gpt-4.1"))
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage", {})
        usage = Usage(
            tokens_in=int(usage_raw.get("prompt_tokens", 0)),
            tokens_out=int(usage_raw.get("completion_tokens", 0)),
        )
        if schema is not None:
            return json.loads(text.strip()), usage
        return text.strip(), usage


def log_usage(events, node, slice: str, usage: Usage) -> None:
    """Attach token costs to the next research/cache event via cost field."""
    events.emit(
        "research_source",
        id=f"usage-{node}-{slice}",
        title="llm usage",
        node=node,
        cost=cost_dict(
            Cost(
                gpu_s=0.0,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                slice=slice,  # type: ignore[arg-type]
            )
        ),
        summary=(
            f"llm {slice}: {usage.tokens_in} in / {usage.tokens_out} out tokens"
        ),
    )
