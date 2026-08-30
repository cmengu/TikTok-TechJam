"""Step 9: lesson schema, forbidden fold, prompt render."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.agents.cache import ResearchCache
from harness.agents.llm import FakeLLM, Usage
from harness.agents.researcher import propose
from harness.events import EventLog
from harness.feedback import (
    DEFECTS,
    admissible,
    feedback_from,
    first_round,
    forbidden,
    format_lesson,
    load_lessons,
    render,
    write_lesson,
)
from harness.types import Hypothesis


def _hyp(**kw) -> Hypothesis:
    defaults = dict(
        id="h-x",
        stage="features",
        mechanism="bad-feat",
        description="x",
        citation="no prior",
        expected_gain=0.01,
        expected_gpu_h=0.1,
        parent_node=None,
        patch=None,
        pattern="bad-feat",
        p_win=0.01,
    )
    defaults.update(kw)
    return Hypothesis(**defaults)  # type: ignore[arg-type]


def _lesson(**kw) -> dict:
    row = {
        "round": 1,
        "node": 2,
        "family": "features/bad-feat",
        "pattern": "bad-feat",
        "defect": "crash",
        "delta": None,
        "verdict": "rejected",
    }
    row.update(kw)
    return row


def _events(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "run", "mem", placeholder_protocol(tmp_path))


def test_lesson_survives_the_round_trip(tmp_path: Path):
    path = tmp_path / "lessons.jsonl"
    write_lesson(path, _lesson(defect="crash", pattern="bad-feat", round=3, delta=-0.01))
    rows = load_lessons(path)
    line = format_lesson(rows[-1])
    assert line.startswith("- [crash] bad-feat")
    assert "round 3" in line
    assert "- lesson: " not in line
    assert "heading" not in rows[-1]
    assert "text" not in rows[-1]


def test_defect_class_is_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown defect"):
        write_lesson(tmp_path / "lessons.jsonl", _lesson(defect="oops"))
    assert DEFECTS == {
        "crash",
        "diverged",
        "timeout",
        "silently_drops_rows",
        "leak_suspected",
        "no_gain",
    }


def test_no_gain_is_not_forbidden():
    lessons = [
        _lesson(pattern="quiet", defect="no_gain", verdict="rejected"),
        _lesson(pattern="boom", defect="crash", verdict="rejected"),
    ]
    forb = forbidden(lessons)
    assert "quiet" not in forb
    assert "boom" in forb
    assert admissible(_hyp(pattern="quiet"), forb) is True
    assert admissible(_hyp(pattern="boom"), forb) is False


def test_forbidden_filter_precedes_the_llm(tmp_path: Path):
    events = _events(tmp_path)
    cache = ResearchCache(
        placeholder_protocol(tmp_path).protocol_hash, events=events
    )
    lessons = [_lesson(pattern="bad-feat", defect="crash", verdict="rejected", round=4)]
    llm = FakeLLM({"researcher": [({"stage": "features"}, Usage(1, 1))]})
    out = propose(
        llm, "brief", "inc", {}, lessons, cache, candidate=_hyp(pattern="bad-feat")
    )
    assert out is None
    assert llm.calls == 0
    events.drain()
    trips = [
        json.loads(l)
        for l in (tmp_path / "run" / "events.jsonl").read_text().splitlines()
        if l.strip() and json.loads(l).get("type") == "rule_trip"
    ]
    assert trips and trips[-1]["rule"] == "forbidden_pattern"
    assert trips[-1]["round"] == 4


def test_forbidden_is_a_fold(tmp_path: Path):
    path = tmp_path / "lessons.jsonl"
    rows = [
        _lesson(pattern="a", defect="crash", verdict="rejected"),
        _lesson(pattern="b", defect="no_gain", verdict="rejected"),
        _lesson(pattern="c", defect="timeout", verdict="rejected"),
    ]
    for r in rows:
        write_lesson(path, r)
    live = forbidden(rows)
    rebuilt = forbidden(load_lessons(path))
    assert live == rebuilt
    again = forbidden(load_lessons(path))
    assert again == live


def test_render_has_exactly_three_headings():
    fb = feedback_from([
        _lesson(pattern="boom", family="features/boom", defect="crash"),
        _lesson(pattern="quiet", family="features/quiet", defect="no_gain"),
    ])
    text = render(fb)
    heads = [ln for ln in text.splitlines() if ln in ("weak components", "directions", "forbidden")]
    assert heads == ["weak components", "directions", "forbidden"]
    assert text.count("weak components") == 1
    assert "boom" in text


def test_prompt_contains_no_raw_event_json(tmp_path: Path):
    events = _events(tmp_path)
    cache = ResearchCache(
        placeholder_protocol(tmp_path).protocol_hash, events=events
    )
    lessons = [_lesson(pattern="keep-out", defect="crash", verdict="rejected")]
    payload = {
        "stage": "features",
        "mechanism": "fresh-feat",
        "pattern": "fresh-feat",
        "description": "new idea",
        "citation": "no prior",
        "expected_gain": 0.02,
        "expected_gpu_h": 0.1,
    }
    llm = FakeLLM({"researcher": [(payload, Usage(3, 5))]})
    events.emit(
        "hypothesis_queued",
        id="already",
        stage="features",
        mechanism="already",
        description="queued so bank seed is skipped",
        expected_gain=0.01,
        expected_gpu_h=0.1,
        parent_node=None,
        summary="queued already",
    )
    events.drain()
    hyp = propose(llm, "brief", "incumbent", {}, lessons, cache)
    assert hyp is not None
    prompt = llm.prompts["researcher"][-1]
    assert '"type":' not in prompt
    assert '"seq":' not in prompt
    assert "- lesson: " not in prompt
    assert "[crash] keep-out" in prompt


def test_first_round_names_the_originating_round():
    lessons = [
        _lesson(pattern="boom", round=2),
        _lesson(pattern="boom", round=7),
    ]
    assert first_round(lessons, "boom") == 2
