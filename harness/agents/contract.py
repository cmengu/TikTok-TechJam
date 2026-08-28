"""Phase 7: static contract checks on generated diffs (no LLM review)."""

from __future__ import annotations

import re

# Capability: forbidden paths in prompts and diffs.
FORBIDDEN_PATH_FRAGMENTS = (
    "protocols/",
    "measure.py",
    "rulebook",
    "holdout",
)

# Diff-only patterns: candidate-side leakage guards (not OOF encoding heuristics).
_DIFF_PATTERNS = (
    re.compile(r"train_test_split\s*\("),
    re.compile(r"""valid_cols\[\s*['"]click['"]\s*\]"""),
    re.compile(r"""valid_cols\[\s*['"]conversion['"]\s*\]"""),
    re.compile(r"""holdout_cols\[\s*['"]click['"]\s*\]"""),
    re.compile(r"""holdout_cols\[\s*['"]conversion['"]\s*\]"""),
)


def check_prompt_capability(prompt: str) -> list[str]:
    errors: list[str] = []
    for frag in FORBIDDEN_PATH_FRAGMENTS:
        if frag in prompt:
            errors.append(f"forbidden path fragment in prompt: {frag!r}")
    return errors


def check_diff_contract(diff: str) -> list[str]:
    errors: list[str] = []
    for frag in FORBIDDEN_PATH_FRAGMENTS:
        if frag in diff:
            errors.append(f"forbidden path fragment in diff: {frag!r}")
    for pat in _DIFF_PATTERNS:
        if pat.search(diff):
            errors.append(f"forbidden pattern in diff: {pat.pattern}")
    return errors
