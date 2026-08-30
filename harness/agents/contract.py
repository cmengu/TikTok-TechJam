"""Phase 7 capability checks — every pattern now lives in candidate/rules.jsonl.

This module used to carry its own copy of the constraints (a tuple of forbidden
path fragments and a list of compiled diff patterns), which meant the contract a
candidate was handed and the contract it was actually held to were two different
documents. Both are now `check: static` rules with `applies_to` scopes, and this
module is a thin adapter over `harness.verify.omega`.
"""

from __future__ import annotations

from functools import lru_cache

from harness.verify import Trip, load_rules, omega


@lru_cache(maxsize=1)
def _rules() -> tuple[dict, ...]:
    return tuple(load_rules())


def _messages(trips: list[Trip], where: str) -> list[str]:
    return [f"{t.rule_id} in {where}: {t.statement}" for t in trips]


def check_prompt_capability(prompt: str) -> list[str]:
    """Rules scoped to `prompt` — the harness-only paths a coder may never see."""
    return _messages(omega(prompt, _rules(), scope="prompt"), "prompt")


def check_diff_contract(diff: str) -> list[str]:
    """Rules scoped to `diff` — every `forbid` rule, plus the paths.

    `require` rules are deliberately absent: a diff hunk is a fragment, and the
    line a `require` rule wants may simply sit outside it. Those are checked
    against the whole post-patch source by `harness.verify.cascade`.
    """
    return _messages(omega(diff, _rules(), scope="diff"), "diff")
