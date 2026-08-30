"""Phase 7: research pass that proposes a schema-validated hypothesis."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import yaml

from harness.agents.cache import ResearchCache
from harness.agents._util import cost_dict
from harness.feedback import (
    admissible,
    feedback_from,
    first_round,
    forbidden,
    format_lesson,
    render,
)
from harness.types import Cost, Hypothesis

REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_PATH = REPO_ROOT / "hypotheses" / "bank.yaml"

STAGES: set[str] = {
    "data",
    "features",
    "objective",
    "architecture",
    "training",
    "ensemble",
}

HYPOTHESIS_SCHEMA = {
    "stage": "one of data|features|objective|architecture|training|ensemble",
    "mechanism": "slug",
    "description": "str",
    "citation": "str or no prior",
    "expected_gain": "number",
    "expected_gpu_h": "number",
    "pattern": "slug",
}


def load_bank(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or BANK_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return list(raw)


def _queued_families(cache: ResearchCache) -> set[str]:
    if cache.events is None:
        return set()
    drain = getattr(cache.events, "drain", None)
    if callable(drain):
        drain()
    path = Path(cache.events._run_dir) / "events.jsonl"  # noqa: SLF001
    if not path.is_file():
        return set()
    families: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("type") == "hypothesis_queued":
            families.add(f"{ev.get('stage')}/{ev.get('mechanism')}")
    return families


def _bank_to_hypothesis(row: dict[str, Any]) -> Hypothesis:
    return Hypothesis(
        id=str(row.get("id") or f"bank-{row['mechanism']}-{uuid.uuid4().hex[:8]}"),
        stage=row["stage"],  # type: ignore[arg-type]
        mechanism=str(row["mechanism"]),
        description=str(row["description"]),
        citation=str(row.get("citation") or "no prior"),
        expected_gain=float(row.get("expected_gain") or 0.0),
        expected_gpu_h=float(row.get("expected_gpu_h") or 0.1),
        parent_node=row.get("parent_node"),
        patch=None,
        pattern=str(row.get("pattern") or row["mechanism"]),
        p_win=float(row.get("p_win") or row.get("expected_gain") or 0.0),
    )


def _validate_payload(data: dict[str, Any]) -> str | None:
    if not isinstance(data, dict):
        return "response is not an object"
    stage = data.get("stage")
    if stage not in STAGES:
        return f"invalid stage: {stage!r}"
    mechanism = data.get("mechanism")
    if not isinstance(mechanism, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", mechanism):
        return f"invalid mechanism slug: {mechanism!r}"
    for field in ("description", "citation"):
        if not isinstance(data.get(field), str) or not str(data[field]).strip():
            return f"missing {field}"
    if data.get("expected_gain") is None:
        return "missing expected_gain"
    try:
        float(data["expected_gain"])
        float(data.get("expected_gpu_h", 0.1))
    except (TypeError, ValueError):
        return "expected_gain/expected_gpu_h must be numbers"
    return None


def _payload_to_hypothesis(data: dict[str, Any]) -> Hypothesis:
    return Hypothesis(
        id=str(data.get("id") or f"hyp-{uuid.uuid4().hex[:8]}"),
        stage=data["stage"],  # type: ignore[arg-type]
        mechanism=str(data["mechanism"]),
        description=str(data["description"]),
        citation=str(data.get("citation") or "no prior"),
        expected_gain=float(data["expected_gain"]),
        expected_gpu_h=float(data.get("expected_gpu_h") or 0.1),
        parent_node=data.get("parent_node"),
        patch=None,
        pattern=str(data.get("pattern") or data["mechanism"]),
        p_win=float(data.get("p_win") or data.get("expected_gain") or 0.0),
        tokens_in=0,
        tokens_out=0,
    )


def _emit_citations(events, node_id: int | None, citations: list[str], usage_slice: str, usage) -> None:
    if events is None:
        return
    for i, title in enumerate(citations):
        payload: dict[str, Any] = {
            "id": f"src-{node_id}-{i}",
            "title": title,
            "summary": f"research source: {title}",
        }
        if node_id is not None:
            payload["node"] = node_id
        if usage is not None:
            payload["cost"] = cost_dict(
                Cost(0.0, usage.tokens_in, usage.tokens_out, usage_slice)  # type: ignore[arg-type]
            )
        events.emit("research_source", **payload)


def _refuse_forbidden(events, hyp: Hypothesis, lessons: list[dict]) -> None:
    rnd = first_round(lessons, hyp.pattern or hyp.mechanism)
    if events is None:
        return
    events.emit(
        "rule_trip",
        rule="forbidden_pattern",
        pattern=hyp.pattern or hyp.mechanism,
        round=rnd,
        summary=f"forbidden pattern {hyp.pattern or hyp.mechanism} first seen round {rnd}",
    )


def propose(
    llm,
    brief: str,
    incumbent_summary: str,
    family_stats,
    lessons: list[dict],
    cache: ResearchCache,
    candidate: Hypothesis | None = None,
) -> Hypothesis | None:
    events = cache.events
    node_id = cache.node_id
    tried = _queued_families(cache)
    forb = forbidden(lessons)

    if candidate is not None:
        if not admissible(candidate, forb):
            _refuse_forbidden(events, candidate, lessons)
            return None
        cache.get(f"{candidate.stage}/{candidate.mechanism}")
        return candidate

    # Empty log: seed from bank (feature-side first), skipping forbidden patterns.
    if not tried:
        for row in load_bank():
            if row.get("stage") != "features":
                continue
            fam = f"{row['stage']}/{row['mechanism']}"
            if fam not in tried:
                hyp = _bank_to_hypothesis(row)
                if not admissible(hyp, forb):
                    _refuse_forbidden(events, hyp, lessons)
                    continue
                cache.get(f"{hyp.stage}/{hyp.mechanism}")
                return hyp

    bank_lines = []
    for row in load_bank():
        fam = f"{row['stage']}/{row['mechanism']}"
        if fam not in tried:
            bank_lines.append(
                f"- {fam}: {row['description']} "
                f"(gain≈{row.get('expected_gain', 0)}, gpu_h≈{row.get('expected_gpu_h', 0.1)})"
            )

    stats_lines = [
        f"  {fam}: n={row.get('n', 0)} mean_delta={row.get('mean_delta', 0):.4f}"
        for fam, row in sorted(family_stats.items())
    ]
    lesson_lines = [format_lesson(l) for l in lessons[-30:] if "defect" in l and "pattern" in l]
    fb = render(feedback_from(lessons))

    prompt = (
        f"{brief}\n\n"
        f"Incumbent:\n{incumbent_summary}\n\n"
        f"Family stats:\n" + ("\n".join(stats_lines) or "  (none)") + "\n\n"
        f"Lessons:\n" + ("\n".join(lesson_lines) or "  (none)") + "\n\n"
        f"{fb}\n\n"
        f"Bank (not yet tried):\n" + ("\n".join(bank_lines) or "  (none)") + "\n\n"
        "Propose one hypothesis as JSON matching the schema."
    )

    cache.get("features/target-encoding")

    data, usage = llm.complete("researcher", prompt, HYPOTHESIS_SCHEMA)

    err = _validate_payload(data if isinstance(data, dict) else {})
    if err:
        if events is not None:
            events.emit(
                "rule_trip",
                rule="hypothesis_schema",
                id="propose",
                summary=f"schema reject: {err}",
            )
        return None

    hyp = _payload_to_hypothesis(data)  # type: ignore[arg-type]
    hyp.tokens_in = int(usage.tokens_in)
    hyp.tokens_out = int(usage.tokens_out)
    if not admissible(hyp, forb):
        _refuse_forbidden(events, hyp, lessons)
        return None
    citations = data.get("citations") or []
    if isinstance(citations, str):
        citations = [citations]
    if isinstance(citations, list) and citations:
        _emit_citations(events, node_id, [str(c) for c in citations], "researching", usage)
    elif str(hyp.citation) != "no prior":
        _emit_citations(events, node_id, [hyp.citation], "researching", usage)

    if events is not None:
        events.drain()
    return hyp
