"""Phase 7: agent module tests (FakeLLM only — no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.agents.brief import compose
from harness.agents.cache import ResearchCache
from harness.agents.coder import LLMCoder
from harness.agents.llm import FakeLLM, Usage
from harness.agents.researcher import load_bank, propose
from harness.events import EventLog
from harness.tree import Workspace
from harness.types import Cost, Hypothesis, Node

ROOT = Path(__file__).resolve().parents[1]

GOOD_DIFF = """\
--- a/template.py
+++ b/template.py
@@ -137,7 +137,7 @@
     workspace.mkdir(parents=True, exist_ok=True)
     os.environ["WORKSPACE"] = str(workspace)
 
-    features = _parse_features(os.environ.get("FEATURES"))
+    features = _parse_features("base,f_true")
     batch_size = int(os.environ.get("BATCH", "4096"))
     lr = float(os.environ.get("LR", "1e-3"))
     epochs = int(os.environ.get("EPOCHS", "1"))
"""

BAD_DIFF = """\
--- a/template.py
+++ b/template.py
@@ -1,1 +1,1 @@
-not a valid diff
+broken
"""


def _usage() -> Usage:
    return Usage(tokens_in=12, tokens_out=34)


def _node() -> Node:
    return Node(
        id=7,
        parent=None,
        hypothesis_id="h-1",
        commit=None,
        state="running",
        rung="screen",
        kind="improve",
        scores={},
        seeds=[1],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=7,
    )


def _hyp() -> Hypothesis:
    return Hypothesis(
        id="h-coder",
        stage="features",
        mechanism="target-encoding",
        description="add target encoding",
        citation="no prior",
        expected_gain=0.02,
        expected_gpu_h=0.1,
        parent_node=None,
        patch=None,
    )


def _events(tmp_path: Path) -> EventLog:
    protocol = placeholder_protocol(tmp_path)
    run_dir = tmp_path / "run"
    return EventLog(run_dir, "test-run", protocol)


def _queue_all_bank(events: EventLog) -> None:
    for row in load_bank():
        events.emit(
            "hypothesis_queued",
            id=row["id"],
            stage=row["stage"],
            mechanism=row["mechanism"],
            description=row["description"],
            expected_gain=float(row.get("expected_gain") or 0),
            expected_gpu_h=float(row.get("expected_gpu_h") or 0.1),
            parent_node=None,
            summary=f"queued {row['id']}",
        )


def _read_events(events: EventLog) -> list[dict]:
    events.drain()
    path = Path(events._run_dir) / "events.jsonl"  # noqa: SLF001
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_valid_proposal_becomes_hypothesis(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events, node_id=3)
    payload = {
        "stage": "features",
        "mechanism": "target-encoding",
        "description": "OOF target encoding on categoricals",
        "citation": "no prior",
        "expected_gain": 0.02,
        "expected_gpu_h": 0.1,
        "claim": {
            "mechanism": "target-encoding",
            "observables": [
                {"name": "gauc", "source": "harness", "direction": "positive"}
            ],
        },
    }
    llm = FakeLLM({"researcher": [(payload, _usage())]})
    hyp = propose(llm, "brief", "incumbent", {}, [], cache)
    assert hyp is not None
    assert hyp.stage == "features"
    assert hyp.mechanism == "target-encoding"
    assert f"{hyp.stage}/{hyp.mechanism}" == "features/target-encoding"


def test_missing_expected_gain_rejected(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events)
    payload = {
        "stage": "features",
        "mechanism": "target-encoding",
        "description": "missing gain",
        "citation": "no prior",
        "expected_gpu_h": 0.1,
    }
    llm = FakeLLM({"researcher": [(payload, _usage())]})
    assert propose(llm, "brief", "incumbent", {}, [], cache) is None
    rows = [e for e in _read_events(events) if e["type"] == "rule_trip"]
    assert rows and rows[-1]["rule_id"] == "hypothesis_schema"


def test_bad_stage_rejected(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events)
    payload = {
        "stage": "method",
        "mechanism": "bad",
        "description": "nope",
        "citation": "no prior",
        "expected_gain": 0.01,
        "expected_gpu_h": 0.1,
    }
    llm = FakeLLM({"researcher": [(payload, _usage())]})
    assert propose(llm, "brief", "incumbent", {}, [], cache) is None


def test_bank_seeds_first_proposals(tmp_path: Path):
    events = _events(tmp_path)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events)
    llm = FakeLLM()
    hyp = propose(llm, "brief", "incumbent", {}, [], cache)
    assert hyp is not None
    assert hyp.stage == "features"
    feature_fams = {
        f"{r['stage']}/{r['mechanism']}"
        for r in load_bank()
        if r.get("stage") == "features"
    }
    assert f"{hyp.stage}/{hyp.mechanism}" in feature_fams


def test_research_events_emitted(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events, node_id=9)
    payload = {
        "stage": "features",
        "mechanism": "cross-stats",
        "description": "cross stats",
        "citation": "no prior",
        "expected_gain": 0.02,
        "expected_gpu_h": 0.1,
        "citations": ["Paper A", "Paper B"],
        "claim": {
            "mechanism": "cross-stats",
            "observables": [
                {"name": "gauc", "source": "harness", "direction": "positive"}
            ],
        },
    }
    llm = FakeLLM({"researcher": [(payload, _usage())]})
    propose(llm, "brief", "incumbent", {}, [], cache)
    sources = [e for e in _read_events(events) if e["type"] == "research_source"]
    assert len(sources) == 2
    for ev in sources:
        assert ev.get("node") == 9
        cost = ev.get("cost")
        assert cost is not None
        assert cost["slice"] == "researching"
        assert cost["tokens_in"] > 0
        assert cost["tokens_out"] > 0


def test_coder_applies_diff(tmp_path: Path):
    events = _events(tmp_path)
    ws = Workspace(tmp_path / "run", "test-run")
    llm = FakeLLM({"coder": [(GOOD_DIFF, _usage())]})
    coder = LLMCoder(llm, ws, events=events)
    path = coder.materialise(_hyp(), _node(), None)
    assert path.read_text(encoding="utf-8") == GOOD_DIFF
    sha = ws.commit_node(1, path)
    assert sha


def test_coder_retries_on_apply_failure(tmp_path: Path):
    events = _events(tmp_path)
    ws = Workspace(tmp_path / "run2", "test-run2")
    llm = FakeLLM({"coder": [(BAD_DIFF, _usage()), (GOOD_DIFF, _usage())]})
    coder = LLMCoder(llm, ws, events=events)
    path = coder.materialise(_hyp(), _node(), None)
    assert path.read_text(encoding="utf-8") == GOOD_DIFF
    assert len(llm.prompts["coder"]) == 2
    assert "Previous error" in llm.prompts["coder"][1]


def test_coder_prompt_capability(tmp_path: Path):
    events = _events(tmp_path)
    ws = Workspace(tmp_path / "run3", "test-run3")
    llm = FakeLLM({"coder": [(GOOD_DIFF, _usage())]})
    coder = LLMCoder(llm, ws, events=events)
    coder.materialise(_hyp(), _node(), None)
    prompt = llm.prompts["coder"][0]
    for forbidden in ("protocols/", "measure.py", "rulebook", "holdout"):
        assert forbidden not in prompt


def test_cache_hit_same_hash_miss_other_hash(tmp_path: Path):
    protocol = placeholder_protocol(tmp_path)
    h1 = protocol.protocol_hash
    cache = ResearchCache(h1, path=tmp_path / "cache.jsonl")
    assert cache.get("features/target-encoding") == (False, None)
    cache.put("features/target-encoding", "confirmed")
    hit, outcome = cache.get("features/target-encoding")
    assert hit is True
    assert outcome == "confirmed"

    cache2 = ResearchCache("different-protocol-hash", path=tmp_path / "cache2.jsonl")
    hit2, outcome2 = cache2.get("features/target-encoding")
    assert hit2 is False
    assert outcome2 is None


def test_brief_deterministic(tmp_path: Path):
    protocol = placeholder_protocol(tmp_path)
    text_path = ROOT / "context" / "Backend_plan.md"
    a = compose(text_path, protocol)
    b = compose(text_path, protocol)
    assert a == b
    assert "protocol.task=" in a


# --- ClaudeCLILLM: headless `claude -p` adapter, subprocess mocked — no CLI ---


def _cli_envelope(result: str, **usage) -> str:
    base = {
        "input_tokens": 10,
        "cache_creation_input_tokens": 700,
        "cache_read_input_tokens": 1300,
        "output_tokens": 54,
    }
    base.update(usage)
    return json.dumps({"is_error": False, "result": result, "usage": base})


class _FakeProc:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_claude_cli_parses_result_and_usage(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _FakeProc(_cli_envelope("--- a/x\n+++ b/x\n"))

    monkeypatch.setattr(llm_mod.subprocess, "run", fake_run)
    adapter = llm_mod.ClaudeCLILLM()
    text, usage = adapter.complete("coder", "write a diff", None)
    assert text == "--- a/x\n+++ b/x"
    # tokens_in counts fresh + cache-written + cache-read: all were processed
    assert usage.tokens_in == 10 + 700 + 1300
    assert usage.tokens_out == 54
    assert seen["cmd"][:2] == ["claude", "-p"]
    assert "--output-format" in seen["cmd"] and "json" in seen["cmd"]
    # the coder role rides the coder model
    assert seen["cmd"][seen["cmd"].index("--model") + 1] == "claude-haiku-4-5-20251001"


def test_claude_cli_schema_parses_json_and_strips_fences(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.agents import llm as llm_mod

    fenced = "```json\n{\"pattern\": \"features/x\"}\n```"
    monkeypatch.setattr(
        llm_mod.subprocess, "run", lambda cmd, **kw: _FakeProc(_cli_envelope(fenced))
    )
    data, _usage = llm_mod.ClaudeCLILLM().complete(
        "researcher", "propose", {"type": "object"}
    )
    assert data == {"pattern": "features/x"}


def test_claude_cli_error_envelope_raises(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    envelope = json.dumps({"is_error": True, "result": "usage limit reached"})
    monkeypatch.setattr(
        llm_mod.subprocess, "run", lambda cmd, **kw: _FakeProc(envelope)
    )
    with pytest.raises(RuntimeError, match="usage limit"):
        llm_mod.ClaudeCLILLM().complete("researcher", "propose", None)


def test_claude_cli_nonzero_exit_raises(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    monkeypatch.setattr(
        llm_mod.subprocess,
        "run",
        lambda cmd, **kw: _FakeProc("", returncode=1, stderr="boom"),
    )
    with pytest.raises(RuntimeError, match="exited 1"):
        llm_mod.ClaudeCLILLM().complete("researcher", "propose", None)


def test_claude_cli_missing_binary_raises(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    def raise_missing(cmd, **kwargs):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(llm_mod.subprocess, "run", raise_missing)
    with pytest.raises(RuntimeError, match="not installed"):
        llm_mod.ClaudeCLILLM().complete("researcher", "propose", None)


def test_claude_cli_judge_rejects_numbers(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    monkeypatch.setattr(
        llm_mod.subprocess, "run", lambda cmd, **kw: _FakeProc(_cli_envelope("3"))
    )
    with pytest.raises(ValueError, match="number"):
        llm_mod.ClaudeCLILLM().judge("diff", ["statement"])


def test_make_llm_selects_by_environment(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    monkeypatch.setenv("HARNESS_LLM", "claude-cli")
    assert isinstance(llm_mod.make_llm(), llm_mod.ClaudeCLILLM)

    monkeypatch.setenv("HARNESS_LLM", "api")
    assert isinstance(llm_mod.make_llm(), llm_mod.AnthropicLLM)

    # unset: the API key wins over an installed CLI
    monkeypatch.delenv("HARNESS_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(llm_mod.make_llm(), llm_mod.AnthropicLLM)

    # unset, no key: an installed claude CLI is the subscription fallback
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_mod.shutil, "which", lambda name: "/usr/local/bin/claude")
    assert isinstance(llm_mod.make_llm(), llm_mod.ClaudeCLILLM)

    # unset, no key, no CLI: AnthropicLLM, whose first call raises the
    # missing-key error — make_llm itself never raises
    monkeypatch.setattr(llm_mod.shutil, "which", lambda name: None)
    assert isinstance(llm_mod.make_llm(), llm_mod.AnthropicLLM)


def test_claude_cli_strips_fences_from_diff(monkeypatch: pytest.MonkeyPatch):
    # The failure seen on the first real run: a fenced diff reached git apply.
    from harness.agents import llm as llm_mod

    fenced = "```diff\n--- a/template.py\n+++ b/template.py\n@@ -1 +1 @@\n-x\n+y\n```"
    monkeypatch.setattr(
        llm_mod.subprocess, "run", lambda cmd, **kw: _FakeProc(_cli_envelope(fenced))
    )
    text, _usage = llm_mod.ClaudeCLILLM().complete("coder", "write a diff", None)
    assert text.startswith("--- a/template.py")
    assert "```" not in text


def test_claude_cli_unfenced_diff_unchanged(monkeypatch: pytest.MonkeyPatch):
    from harness.agents import llm as llm_mod

    plain = "--- a/t.py\n+++ b/t.py\n@@ -1 +1 @@\n-x\n+y"
    monkeypatch.setattr(
        llm_mod.subprocess, "run", lambda cmd, **kw: _FakeProc(_cli_envelope(plain))
    )
    text, _usage = llm_mod.ClaudeCLILLM().complete("coder", "write a diff", None)
    assert text == plain


def _cite_payload(citations: list[str]) -> dict:
    return {
        "stage": "features",
        "mechanism": "cross-stats",
        "description": "cross stats",
        "citation": "no prior",
        "expected_gain": 0.02,
        "expected_gpu_h": 0.1,
        "citations": citations,
        "claim": {
            "mechanism": "cross-stats",
            "observables": [
                {"name": "gauc", "source": "harness", "direction": "positive"}
            ],
        },
    }


def test_citation_url_lands_on_event(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events, node_id=9)
    llm = FakeLLM(
        {
            "researcher": [
                (
                    _cite_payload(
                        ["Wide & Deep (https://arxiv.org/abs/1606.07792)"]
                    ),
                    _usage(),
                )
            ]
        }
    )
    propose(llm, "brief", "incumbent", {}, [], cache)
    sources = [e for e in _read_events(events) if e["type"] == "research_source"]
    assert len(sources) == 1
    assert sources[0]["title"] == "Wide & Deep"
    assert sources[0]["url"] == "https://arxiv.org/abs/1606.07792"


def test_citation_without_url_unchanged(tmp_path: Path):
    events = _events(tmp_path)
    _queue_all_bank(events)
    protocol = placeholder_protocol(tmp_path)
    cache = ResearchCache(protocol.protocol_hash, events=events, node_id=9)
    llm = FakeLLM({"researcher": [(_cite_payload(["Paper A"]), _usage())]})
    propose(llm, "brief", "incumbent", {}, [], cache)
    sources = [e for e in _read_events(events) if e["type"] == "research_source"]
    assert len(sources) == 1
    assert sources[0]["title"] == "Paper A"
    assert "url" not in sources[0]


def test_fixture_still_l4v_four_nodes():
    from harness.outputs import claim_level

    path = ROOT / "tests" / "fixtures" / "fake-events.jsonl"
    events = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    assert claim_level(events) == "L4-v"
    nodes = {e["id"] for e in events if e["type"] == "node_created"}
    assert len(nodes) == 4
