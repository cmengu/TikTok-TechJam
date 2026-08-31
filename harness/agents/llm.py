"""Phase 7: LLM adapters and usage logging."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        self.calls = 0

    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        self.calls += 1
        self.prompts.setdefault(role, []).append(prompt)
        bucket = self._scripts.get(role, [])
        idx = self._cursor.get(role, 0)
        if idx >= len(bucket):
            raise RuntimeError(f"FakeLLM exhausted for role {role!r}")
        self._cursor[role] = idx + 1
        return bucket[idx]

    def judge(self, diff: str, statements: list[str]) -> dict[str, Any]:
        """One boolean per statement. Defaults to all-true when unscripted."""
        prompt = "judge\n" + "\n".join(statements) + "\n\n" + diff
        bucket = self._scripts.get("judge", [])
        idx = self._cursor.get("judge", 0)
        self.prompts.setdefault("judge", []).append(prompt)
        if idx < len(bucket):
            self._cursor["judge"] = idx + 1
            payload, _usage = bucket[idx]
            self.calls += 1
            if isinstance(payload, dict):
                return payload
            return {s: bool(payload) for s in statements}
        self.calls += 1
        return {s: True for s in statements}


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

    def judge(self, diff: str, statements: list[str]) -> dict[str, Any]:
        prompt = (
            "For each statement, return JSON mapping the statement to a boolean "
            "and the line you relied on. Booleans only — no numbers.\n"
            + json.dumps(statements)
            + "\n\nDiff:\n"
            + diff
        )
        data, _usage = self.complete("judge", prompt, {"type": "object"})
        if not isinstance(data, dict):
            raise ValueError("semantic judge returned a number")
        return data


def _strip_fences(text: str) -> str:
    """Drop a single wrapping ```/```json fence pair if the model added one."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


class ClaudeCLILLM:
    """Headless Claude Code (`claude -p`) adapter — runs on the user's
    subscription instead of an API key. Same surface as AnthropicLLM."""

    def __init__(self, models: dict[str, str] | None = None) -> None:
        self.models = models or {
            "researcher": "claude-sonnet-5",
            "coder": "claude-haiku-4-5-20251001",
        }

    def complete(
        self, role: str, prompt: str, schema: dict | None
    ) -> tuple[Any, Usage]:
        model = self.models.get(role, self.models.get("researcher", "claude-sonnet-5"))
        system = (
            "Respond with JSON only, no markdown fences."
            if schema is not None
            else "Respond with a unified diff only, no prose."
        )
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            model,
            "--system-prompt",
            system,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300.0
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "claude CLI is not installed (needed when ANTHROPIC_API_KEY "
                "is not set); install Claude Code or export an API key"
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exited {proc.returncode}: {proc.stderr.strip()[-500:]}"
            )
        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude -p error: {str(data.get('result'))[:500]}")
        text = str(data.get("result", ""))
        usage_raw = data.get("usage", {})
        # The CLI splits the prompt into fresh vs cached prefix tokens; the
        # cost ledger counts tokens processed, so all three land in tokens_in.
        usage = Usage(
            tokens_in=(
                int(usage_raw.get("input_tokens", 0))
                + int(usage_raw.get("cache_creation_input_tokens", 0))
                + int(usage_raw.get("cache_read_input_tokens", 0))
            ),
            tokens_out=int(usage_raw.get("output_tokens", 0)),
        )
        if schema is not None:
            return json.loads(_strip_fences(text)), usage
        # Diff-mode responses get the same treatment: headless Claude wraps
        # unified diffs in ```diff fences despite the system prompt, and a
        # fence line makes git apply reject the whole patch (seen on the
        # first real KuaiRand run — every node trained the unpatched
        # baseline). Stripping here keeps the guarantee at the seam.
        return _strip_fences(text), usage

    def judge(self, diff: str, statements: list[str]) -> dict[str, Any]:
        prompt = (
            "For each statement, return JSON mapping the statement to a boolean "
            "and the line you relied on. Booleans only — no numbers.\n"
            + json.dumps(statements)
            + "\n\nDiff:\n"
            + diff
        )
        data, _usage = self.complete("judge", prompt, {"type": "object"})
        if not isinstance(data, dict):
            raise ValueError("semantic judge returned a number")
        return data


def make_llm(models: dict[str, str] | None = None):
    """Pick the LLM adapter from the environment.

    HARNESS_LLM=claude-cli forces the subscription path, HARNESS_LLM=api the
    key path. Unset: the API key wins if present, else a installed claude CLI,
    else AnthropicLLM (whose first call raises the missing-key error).
    """
    choice = os.environ.get("HARNESS_LLM", "")
    if choice == "claude-cli":
        return ClaudeCLILLM(models=models)
    if choice == "api":
        return AnthropicLLM(models=models)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLM(models=models)
    if shutil.which("claude"):
        return ClaudeCLILLM(models=models)
    return AnthropicLLM(models=models)



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
