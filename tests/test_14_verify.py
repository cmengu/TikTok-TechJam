"""Phase 2 step 7: candidate/rules.jsonl is the only constraint source.

Before this step the rules file had no reader — a second, hardcoded constraint
layer lived in `harness/agents/contract.py`, so the contract a candidate was
handed and the contract it was held to were two different documents. These
tests pin the single source, the scopes, and the cascade's short circuit: a
level-1 trip must cost zero LLM calls and zero runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.types import Cost, Node
from harness.verify import Trip, cascade, load_rules, omega, v_sem

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "candidate" / "kuairand" / "template.py"
CONTRACT = ROOT / "harness" / "agents" / "contract.py"
RULES = ROOT / "candidate" / "rules.jsonl"

# A unified diff that actually reads VALID labels — not the regex's own source.
VALID_LABEL_DIFF = """\
--- a/template.py
+++ b/template.py
@@ -160,6 +160,7 @@
     train_rows = _read_rows(train_path, with_label=True)
     valid_rows = _read_rows(valid_path, with_label=False)
+    leaked = pd.read_csv(os.environ["VALID"])["long_view"]
     if max_rows:
         train_rows = train_rows[: int(max_rows)]
"""

# Everything a require rule wants except report.progress.
NO_PROGRESS_DIFF = """\
--- a/template.py
+++ b/template.py
@@ -1,3 +1,4 @@
+import os
 def train():
     seed = int(os.environ.get("SEED", "0"))
     writer.writerow(["row_id", "user_id", "video_id", "score"])
     report.checkpoint.save(1, b"")
"""

# The literals that lived in contract.py before this step.
MOVED_PATH_FRAGMENTS = ("protocols/", "measure.py", "rulebook", "holdout")
MOVED_DIFF_PATTERNS = (
    r"train_test_split\s*\(",
    r"""valid_cols\[\s*['"]click['"]\s*\]""",
    r"""valid_cols\[\s*['"]conversion['"]\s*\]""",
    r"""holdout_cols\[\s*['"]click['"]\s*\]""",
    r"""holdout_cols\[\s*['"]conversion['"]\s*\]""",
)


class _SpyLLM:
    """A semantic judge that records how many times it was consulted."""

    def __init__(self, answers=None, numeric: bool = False, raises=None) -> None:
        self.calls = 0
        self.answers = answers
        self.numeric = numeric
        self.raises = raises

    def judge(self, diff, statements):  # noqa: ANN001
        del diff
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        if self.numeric:
            return {statements[0]: 0.42, statements[1]: True}
        if self.answers is not None:
            return dict(self.answers)
        return {s: True for s in statements}


class _SpyRunner:
    def __init__(self, ok: bool = True) -> None:
        self.runs = 0
        self.ok = ok

    def run(self, node, rung, seed=1, timeout_s=60.0, **kwargs):  # noqa: ANN001
        del node, rung, seed, timeout_s, kwargs
        self.runs += 1
        outer = self

        class _Res:
            ok = outer.ok
            wall_s = 0.0
            failure_class = None

        return _Res()


def _node(nid: int = 1) -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id="h-1",
        commit=None,
        state="running",
        rung="smoke",
        kind="draft",
        scores={},
        seeds=[1],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=nid,
    )


def _events(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "run", "test-run", placeholder_protocol(tmp_path))


def _read_events(events: EventLog) -> list[dict]:
    events.drain()
    path = Path(events._run_dir) / "events.jsonl"  # noqa: SLF001
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _clean_source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


# --- level 1 -----------------------------------------------------------------

def test_omega_forbid_trips():
    """A realistic diff that reads VALID labels trips C1."""
    trips = omega(VALID_LABEL_DIFF, load_rules(), scope="diff")
    assert [t.rule_id for t in trips] == ["C1"]
    assert trips[0].severity == "fail"
    assert trips[0].statement.startswith("Never reads validation labels")


def test_omega_require_trips():
    """A candidate that never calls report.progress trips C5."""
    trips = omega(NO_PROGRESS_DIFF, load_rules(), scope="source")
    assert [t.rule_id for t in trips] == ["C5"]


def test_shipped_template_trips_nothing():
    assert omega(_clean_source(), load_rules(), scope="source") == []


def test_prompt_scope_sees_only_the_path_rules():
    """A prompt is not a candidate: require rules must never trip on it."""
    rules = load_rules()
    assert omega("Write a unified diff for template.py.", rules, scope="prompt") == []
    trips = omega("first read protocols/kuairand.yaml", rules, scope="prompt")
    assert [t.rule_id for t in trips] == ["C10"]


def test_diff_scope_is_forbid_only():
    """A tiny legal hunk must not trip the require rules it does not contain."""
    assert omega("+    x = 1\n", load_rules(), scope="diff") == []


# --- level 2 -----------------------------------------------------------------

def test_v_sem_rejects_numeric_fields():
    """A judge that answers with a score, not a boolean, is a bug — not a verdict."""
    with pytest.raises(ValueError, match="number"):
        v_sem(VALID_LABEL_DIFF, load_rules(), _SpyLLM(numeric=True))


def test_v_sem_trips_the_rule_the_judge_refused():
    trips = v_sem(NO_PROGRESS_DIFF, load_rules(), _SpyLLM(answers={"C2": False, "C7": True}))
    assert [t.rule_id for t in trips] == ["C2"]


def test_v_sem_fails_open_when_the_judge_is_flaky():
    llm = _SpyLLM(raises=RuntimeError("503 from the provider"))
    assert v_sem(NO_PROGRESS_DIFF, load_rules(), llm) == []
    assert llm.calls == 1


def test_v_sem_without_a_judge_is_skipped():
    assert v_sem(NO_PROGRESS_DIFF, load_rules(), None) == []


# --- the cascade -------------------------------------------------------------

def test_clean_diff_passes_all_levels():
    """The shipped KuaiRand template clears omega, v_sem and the smoke run."""
    llm, runner = _SpyLLM(), _SpyRunner(ok=True)
    ok, level, trips = cascade(
        _clean_source(), load_rules(), llm, runner, _node(), scope="source"
    )
    assert (ok, level, trips) == (True, "accept", [])
    assert llm.calls == 1 and runner.runs == 1


def test_cascade_short_circuits():
    """A level-1 fail costs zero LLM calls and zero runs."""
    llm, runner = _SpyLLM(), _SpyRunner(ok=True)
    ok, level, trips = cascade(
        VALID_LABEL_DIFF, load_rules(), llm, runner, _node(), scope="diff"
    )
    assert ok is False and level == "omega"
    assert [t.rule_id for t in trips] == ["C1"]
    assert llm.calls == 0 and runner.runs == 0


def test_cascade_stops_at_v_sem_before_the_run():
    llm, runner = _SpyLLM(answers={"C2": False, "C7": True}), _SpyRunner(ok=True)
    ok, level, trips = cascade(
        _clean_source(), load_rules(), llm, runner, _node(), scope="source"
    )
    assert ok is False and level == "v_sem"
    assert [t.rule_id for t in trips] == ["C2"]
    assert llm.calls == 1 and runner.runs == 0


def test_cascade_reports_a_failed_smoke_run():
    ok, level, trips = cascade(
        _clean_source(), load_rules(), _SpyLLM(), _SpyRunner(ok=False),
        _node(), scope="source",
    )
    assert (ok, level, trips) == (False, "smoke", [])


def test_cascade_without_a_runner_stops_after_the_static_levels():
    """The tree runs its own smoke rung; a second would buy nothing."""
    llm = _SpyLLM()
    ok, level, trips = cascade(
        _clean_source(), load_rules(), llm, None, _node(), scope="source"
    )
    assert (ok, level, trips) == (True, "static", [])
    assert llm.calls == 1


# --- the events the dashboard renders ----------------------------------------

def test_cascade_emits_one_verify_level_per_level(tmp_path: Path):
    events = _events(tmp_path)
    cascade(
        _clean_source(), load_rules(), _SpyLLM(), _SpyRunner(ok=True), _node(7),
        scope="source", events=events, round_=3,
    )
    levels = [e for e in _read_events(events) if e["type"] == "verify_level"]
    assert [e["level"] for e in levels] == ["omega", "v_sem", "smoke"]
    for ev in levels:
        assert ev["node"] == 7 and ev["round"] == 3
        assert ev["passed"] is True and ev["trips"] == []
    assert [e["llm_calls"] for e in levels] == [0, 1, 0]
    assert [e["runs"] for e in levels] == [0, 0, 1]


def test_cascade_emits_one_rule_trip_per_trip(tmp_path: Path):
    events = _events(tmp_path)
    cascade(
        VALID_LABEL_DIFF, load_rules(), _SpyLLM(), _SpyRunner(), _node(4),
        scope="diff", events=events, round_=2,
    )
    log = _read_events(events)
    trips = [e for e in log if e["type"] == "rule_trip"]
    assert len(trips) == 1
    (ev,) = trips
    assert ev["node"] == 4 and ev["round"] == 2 and ev["level"] == "omega"
    assert ev["rule_id"] == "C1" and ev["severity"] == "fail"
    assert isinstance(ev["statement"], str) and ev["statement"]
    levels = [e for e in log if e["type"] == "verify_level"]
    assert [e["level"] for e in levels] == ["omega"]
    assert levels[0]["passed"] is False and levels[0]["trips"] == ["C1"]


# --- the file is data, not code ----------------------------------------------

def test_rules_file_is_the_only_source():
    """No literal pattern list survives in contract.py."""
    src = CONTRACT.read_text(encoding="utf-8")
    assert "FORBIDDEN_PATH_FRAGMENTS" not in src
    assert "_DIFF_PATTERNS" not in src
    assert "re.compile" not in src
    assert "harness.verify" in src


def test_every_moved_literal_is_now_a_rule():
    blob = "\n".join(r["pattern"] or "" for r in load_rules() if r["check"] == "static")
    for frag in MOVED_PATH_FRAGMENTS:
        assert frag.replace(".", r"\.") in blob, frag
    for pat in MOVED_DIFF_PATTERNS:
        assert pat in blob, pat


def test_a_new_rule_changes_behaviour_with_no_code_edit(tmp_path: Path):
    """The step gate: rules.jsonl is data. Adding a rule changes the verdict."""
    throwaway = {
        "id": "C99", "statement": "Throwaway rule for the step-7 gate.",
        "check": "static", "mode": "forbid", "pattern": "def fit_model",
        "severity": "fail", "source": "seed", "applies_to": ["source"],
    }
    path = tmp_path / "rules.jsonl"
    path.write_text(
        RULES.read_text(encoding="utf-8").rstrip("\n") + "\n"
        + json.dumps(throwaway) + "\n",
        encoding="utf-8",
    )
    src = _clean_source() + "\ndef fit_model():\n    return None\n"
    assert omega(src, load_rules(), scope="source") == []
    assert [t.rule_id for t in omega(src, load_rules(path), scope="source")] == ["C99"]


def test_trip_is_frozen_and_hashable():
    t = Trip("C1", "s", "fail")
    assert {t, Trip("C1", "s", "fail")} == {t}
    with pytest.raises(Exception):
        t.rule_id = "C2"  # type: ignore[misc]
