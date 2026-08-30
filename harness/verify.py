"""Phase 2 step 7: the verification cascade.

`candidate/rules.jsonl` is the single source of the candidate contract. Before
this module it had no reader: a second, hardcoded constraint layer lived in
`harness/agents/contract.py`, so the file a candidate is handed and the checks
a candidate actually faced were two different things.

Three levels, cheapest first, with a real short circuit:

    omega   regex over the declared `check: static` rules   0 LLM calls, 0 runs
    v_sem   ONE LLM call carrying the `check: llm` statements
    smoke   the runner's smoke rung

A `severity: fail` trip at a level stops the cascade there, so a level-1 trip
costs nothing. The semantic level fails **open** with a logged warning when the
judge is unreachable — a flaky provider must not silently reject a candidate —
but a judge that answers with a *number* instead of a boolean raises: a score
is not a verdict, and quietly thresholding one would invent a ruler.

Scopes. A rule declares `applies_to`; the caller declares what it is holding.

    prompt   text sent to the coder LLM        forbidden path fragments only
    diff     a unified diff fragment           forbid + semantic rules
    source   the whole post-patch candidate    every rule, require included

A `require` rule cannot be answered from a diff fragment — the line it wants
may simply be outside the hunk — so require rules are `source` only.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

RULES_PATH = Path(__file__).resolve().parents[1] / "candidate" / "rules.jsonl"
SMOKE_TIMEOUT_S = 60.0
LEVELS = ("omega", "v_sem", "smoke")
SCOPES = ("prompt", "diff", "source")
DEFAULT_SCOPE = "source"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Trip:
    """One rule that did not hold. Never a boolean — always the rule that said so."""

    rule_id: str
    statement: str
    severity: str


def load_rules(path: Path | str = RULES_PATH) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def rules_in_scope(rules: Iterable[dict], scope: str) -> list[dict]:
    if scope not in SCOPES:
        raise ValueError(f"unknown scope: {scope!r}")
    return [r for r in rules if scope in r.get("applies_to", [DEFAULT_SCOPE])]


def omega(diff: str, rules: Sequence[dict], *, scope: str = DEFAULT_SCOPE) -> list[Trip]:
    """Level 1 — regex only. `forbid` that hit, `require` that missed."""
    trips: list[Trip] = []
    for r in rules_in_scope(rules, scope):
        if r["check"] != "static":
            continue
        pattern = r.get("pattern")
        if not pattern:
            continue
        hit = bool(re.search(pattern, diff))
        if (r["mode"] == "forbid") == hit:
            trips.append(Trip(r["id"], r["statement"], r["severity"]))
    return trips


def v_sem(
    diff: str, rules: Sequence[dict], llm: Any, *, scope: str = DEFAULT_SCOPE
) -> list[Trip]:
    """Level 2 — one call carrying every semantic statement in scope.

    Fails open on an unreachable judge; raises on a numeric answer.
    """
    stmts = [r for r in rules_in_scope(rules, scope) if r["check"] == "llm"]
    if not stmts or llm is None:
        return []
    try:
        answers = llm.judge(diff, [r["statement"] for r in stmts])
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — a flaky judge may not reject a candidate
        log.warning("semantic level failed open: %s: %s", type(exc).__name__, exc)
        return []
    if not isinstance(answers, dict):
        raise ValueError(f"semantic judge returned {type(answers).__name__}, not a mapping")
    for value in answers.values():
        if isinstance(value, float) or (
            isinstance(value, int) and not isinstance(value, bool)
        ):
            raise ValueError("semantic judge returned a number, not a boolean")
    trips: list[Trip] = []
    for r in stmts:
        answer = answers.get(r["id"], answers.get(r["statement"]))
        if answer is None:
            log.warning("semantic judge skipped %s; failing open", r["id"])
            continue
        if not answer:
            trips.append(Trip(r["id"], r["statement"], r["severity"]))
    return trips


def _node_id(node: Any) -> Any:
    return getattr(node, "id", node)


def _emit_level(
    events: Any,
    node: Any,
    round_: int,
    level: str,
    trips: Sequence[Trip],
    llm_calls: int,
    runs: int,
) -> None:
    """One `verify_level` per level evaluated, one `rule_trip` per trip."""
    if events is None:
        return
    nid = _node_id(node)
    for t in trips:
        events.emit(
            "rule_trip",
            node=nid,
            level=level,
            rule_id=t.rule_id,
            statement=t.statement,
            severity=t.severity,
            round=round_,
            summary=f"node {nid} {level} trip {t.rule_id}: {t.statement}",
        )
    passed = not any(t.severity == "fail" for t in trips)
    events.emit(
        "verify_level",
        node=nid,
        round=round_,
        level=level,
        passed=passed,
        trips=[t.rule_id for t in trips],
        llm_calls=llm_calls,
        runs=runs,
        summary=(
            f"node {nid} {level} {'passed' if passed else 'failed'} "
            f"({llm_calls} llm, {runs} runs)"
        ),
    )


def cascade(
    diff: str,
    rules: Sequence[dict],
    llm: Any,
    runner: Any,
    node: Any,
    *,
    scope: str = DEFAULT_SCOPE,
    events: Any = None,
    round_: int = 0,
    timeout_s: float = SMOKE_TIMEOUT_S,
) -> tuple[bool, str, list[Trip]]:
    """Run the levels in order and stop at the first `fail`.

    Returns `(ok, level, trips)`. `level` is where it stopped — `"accept"` when
    every level held, or `"static"` when `runner is None` and the smoke rung is
    the caller's own (the tree runs one already; a second would be a real GPU
    hour spent to learn nothing).
    """
    sem_calls = int(
        llm is not None
        and any(r["check"] == "llm" for r in rules_in_scope(rules, scope))
    )
    for level, fn, calls in (
        ("omega", lambda: omega(diff, rules, scope=scope), 0),
        ("v_sem", lambda: v_sem(diff, rules, llm, scope=scope), sem_calls),
    ):
        trips = fn()
        _emit_level(events, node, round_, level, trips, calls, 0)
        if any(t.severity == "fail" for t in trips):
            return False, level, trips  # NO llm call, NO run
    if runner is None:
        return True, "static", []
    res = runner.run(node, "smoke", seed=1, timeout_s=timeout_s)
    ok = bool(getattr(res, "ok", False))
    _emit_level(events, node, round_, "smoke", [], 0, 1)
    return (True, "accept", []) if ok else (False, "smoke", [])
