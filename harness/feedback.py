"""Step 9: closed lesson schema and prompt folds. No run state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from harness.types import Hypothesis

DEFECTS = frozenset({
    "crash",
    "diverged",
    "timeout",
    "silently_drops_rows",
    "leak_suspected",
    "no_gain",
})

_ROW_KEYS = frozenset({"round", "node", "family", "pattern", "defect", "delta", "verdict"})
_HEADINGS = ("weak components", "directions", "forbidden")


@dataclass(frozen=True)
class Feedback:
    weak_components: list[str]
    directions: list[str]
    forbidden: list[str]


def write_lesson(path: Path, row: dict[str, Any]) -> None:
    """Append one closed-schema lesson. Unknown defect raises."""
    defect = row.get("defect")
    if defect not in DEFECTS:
        raise ValueError(f"unknown defect: {defect!r}")
    missing = _ROW_KEYS - row.keys()
    if missing:
        raise ValueError(f"lesson missing keys: {sorted(missing)}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: row[k] for k in sorted(_ROW_KEYS)}, separators=(",", ":")) + "\n")


def load_lessons(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def forbidden(lessons: Iterable[dict[str, Any]]) -> set[str]:
    return {
        str(l["pattern"])
        for l in lessons
        if l.get("verdict") == "rejected" and l.get("defect") != "no_gain"
    }


def admissible(hyp: Hypothesis, forb: set[str]) -> bool:
    """True iff this pattern has not been ruled defective. Call before any token is spent."""
    pattern = hyp.pattern or hyp.mechanism
    return pattern not in forb


def first_round(lessons: Iterable[dict[str, Any]], pattern: str) -> int | None:
    hits = [int(l["round"]) for l in lessons if l.get("pattern") == pattern]
    return min(hits) if hits else None


def feedback_from(lessons: list[dict[str, Any]]) -> Feedback:
    forb = sorted(forbidden(lessons))
    weak: list[str] = []
    seen_fam: set[str] = set()
    for l in lessons:
        fam = str(l.get("family") or "")
        if fam and fam not in seen_fam and l.get("verdict") == "rejected":
            seen_fam.add(fam)
            weak.append(fam)
    directions: list[str] = []
    seen_dir: set[str] = set()
    for l in lessons:
        if l.get("defect") == "no_gain":
            continue
        pat = str(l.get("pattern") or "")
        if not pat or pat in seen_dir:
            continue
        seen_dir.add(pat)
        cite = str(l.get("citation") or "no prior")
        directions.append(f"{pat} ({cite})")
        if len(directions) == 3:
            break
    if not directions:
        directions = ["no prior"]
    return Feedback(weak_components=weak, directions=directions[:3], forbidden=forb)


def render(fb: Feedback) -> str:
    """Exactly three headings, fixed order, no prose."""
    def _block(title: str, items: list[str]) -> str:
        body = "\n".join(f"- {x}" for x in items) if items else "- (none)"
        return f"{title}\n{body}"

    return "\n".join((
        _block(_HEADINGS[0], fb.weak_components),
        _block(_HEADINGS[1], fb.directions),
        _block(_HEADINGS[2], fb.forbidden),
    ))


def format_lesson(lesson: dict[str, Any]) -> str:
    return (
        f"- [{lesson['defect']}] {lesson['pattern']} "
        f"(round {lesson['round']}, delta {lesson['delta']})"
    )
