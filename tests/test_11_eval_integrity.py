"""Step 4: oracle wall, holdout scoring, and promotion-event integrity."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.fake_run import write
from harness.measure import HOLDOUT_SEEDS, HOLDOUT_VISITS_MAX, HoldoutBudgetExceeded, Measure
from harness.runner import RUNG_ENV, Completed, Runner
from harness.tasks.base import TaskPaths
from harness.tasks.kuairand import DATA_DIR, KuaiRandTask
from harness.types import Cost, Node, RunResult

ROOT = Path(__file__).resolve().parents[1]


def _node(nid: int = 1) -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id="h-1",
        commit=None,
        state="running",
        rung="screen",
        kind="draft",
        scores={},
        seeds=[1],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=nid,
    )


def _band():
    from harness.measure import Band

    return Band(
        sigma_screen=0.01,
        sigma_full=0.01,
        sigma_pair=0.01,
        ratio=1.0,
        rho=0.5,
        sd_delta_screen=0.01,
        sd_delta_full=0.01,
        bar=0.011,
        source="fixed_pair",
        n_replicated=0,
    )


@dataclass
class RecordingTask:
    name: str = "synthetic"
    metric: str = "cvr_auc"
    prediction_columns: tuple[str, ...] = ("sample_id",)
    include_oracle_delta: bool = False
    candidate_dir: Path = ROOT / "candidate" / "synthetic"
    splits: list[str] = field(default_factory=list)
    extra_env: dict[str, str] = field(default_factory=dict)

    def candidate_env(self, paths: TaskPaths, *, rung: str = "screen") -> dict[str, str]:
        env = {"TRAIN": str(paths.train), "VALID": str(paths.search_validation)}
        if rung == "holdout" and paths.oracle_features is not None:
            env["ORACLE"] = str(paths.oracle_features)
        env.update(self.extra_env)
        return env

    def score(self, preds_path: Path, split: str) -> dict[str, float]:
        self.splits.append(split)
        return {"cvr_auc": 0.1 if split == "search" else 0.9}

    def submission_features(self) -> Path | None:
        return None

    def rows(self, split: str) -> int:
        return 1


class _OkBackend:
    def run(self, workspace, cmd, env, timeout_s, on_progress) -> Completed:
        del cmd, env, timeout_s, on_progress
        workspace = Path(workspace)
        preds = workspace / "preds.csv"
        preds.write_text("sample_id,p_click,p_conversion_given_click\n0,0.1,0.2\n")
        (workspace / "result.json").write_text(json.dumps({"preds": str(preds)}))
        return Completed(0, "", 0.01)


def _paths(tmp_path: Path) -> TaskPaths:
    train = tmp_path / "train.csv"
    search = tmp_path / "search.csv"
    holdout = tmp_path / "harness_only" / "holdout.csv"
    oracle = tmp_path / "oracle_features.csv"
    holdout.parent.mkdir(parents=True, exist_ok=True)
    for p in (train, search, holdout, oracle):
        p.write_text("x\n")
    return TaskPaths(
        train=train,
        search_validation=search,
        holdout_validation=holdout,
        scoring_script=None,
        oracle_features=oracle,
    )


def test_holdout_rung_scores_holdout(tmp_path: Path):
    assert RUNG_ENV["holdout"].score_split == "holdout"
    src = (ROOT / "harness" / "runner.py").read_text(encoding="utf-8")
    assert 'score(preds, "search")' not in src
    assert "spec.score_split" in src

    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)
    task = RecordingTask()
    paths = _paths(tmp_path)
    runner = Runner(
        events,
        task,
        {"paths": paths, "run_dir": tmp_path / "run", "device": "cpu"},
        backend=_OkBackend(),
        heartbeat_s=60.0,
    )
    try:
        search = runner.run(_node(), "screen", seed=1, timeout_s=5.0)
        holdout = runner.run(_node(), "holdout", seed=1, timeout_s=5.0)
    finally:
        events.close()
    assert search.metrics["cvr_auc"] == 0.1
    assert holdout.metrics["cvr_auc"] == 0.9
    assert holdout.metrics["cvr_auc"] != search.metrics["cvr_auc"]
    assert task.splits == ["search", "holdout"]


def test_candidate_env_allowlist(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)
    task = RecordingTask(extra_env={"LEAK": "1"})
    runner = Runner(
        events,
        task,
        {"paths": _paths(tmp_path), "run_dir": tmp_path / "run", "device": "cpu"},
        backend=_OkBackend(),
        heartbeat_s=60.0,
    )
    try:
        with pytest.raises(AssertionError):
            runner.run(_node(), "screen", seed=1, timeout_s=5.0)
    finally:
        events.close()


@pytest.mark.skipif(not (DATA_DIR / "train.csv").exists(), reason="KuaiRand splits not built")
def test_oracle_labels_never_in_candidate_env():
    from harness.protocol import load as load_protocol

    proto = load_protocol(ROOT / "protocols" / "kuairand.yaml")
    task = KuaiRandTask()
    paths = task.prepare(proto, ROOT / "runs" / "test-data")
    for rung in ("screen", "holdout"):
        env = task.candidate_env(paths, rung=rung)
        for raw in env.values():
            resolved = Path(raw).resolve()
            assert "harness_only" not in resolved.parts, resolved


def test_every_oracle_visit_emits_an_event(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)

    class FakeRunner:
        run_cfg = {"timeout_s": 5.0}
        calls: list = []

        def run(self, node, rung, seed, timeout_s, **kwargs):
            self.calls.append((rung, seed))
            return RunResult(
                node=node.id,
                attempt=1,
                seed=seed,
                rung=rung,
                ok=True,
                metrics={"cvr_auc": 0.56},
                failure_class=None,
                stderr_tail="",
                gpu_s=0.0,
                wall_s=0.1,
                result_path=None,
                checkpoint_path=None,
            )

    measure = Measure(events, proto, _band(), metric="cvr_auc")
    from harness.measure import SeedCache

    inc = SeedCache({s: 0.55 for s in range(1, HOLDOUT_SEEDS + 1)})
    runner = FakeRunner()
    try:
        measure.holdout_report(_node(), runner, inc, 0.5)
        measure.holdout_report(_node(), runner, inc, 0.5)
    finally:
        events.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / "run" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    visits = [e for e in rows if e.get("type") == "measurement" and e.get("rung") == "holdout"]
    assert len(visits) == measure.holdout_visits == 2


def test_oracle_budget_raises(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)

    class FakeRunner:
        run_cfg = {"timeout_s": 5.0}

        def run(self, node, rung, seed, timeout_s, **kwargs):
            return RunResult(
                node=node.id,
                attempt=1,
                seed=seed,
                rung=rung,
                ok=True,
                metrics={"cvr_auc": 0.56},
                failure_class=None,
                stderr_tail="",
                gpu_s=0.0,
                wall_s=0.1,
                result_path=None,
                checkpoint_path=None,
            )

    measure = Measure(events, proto, _band(), metric="cvr_auc")
    from harness.measure import SeedCache

    inc = SeedCache({s: 0.55 for s in range(1, HOLDOUT_SEEDS + 1)})
    runner = FakeRunner()
    try:
        for _ in range(HOLDOUT_VISITS_MAX):
            measure.holdout_report(_node(), runner, inc, 0.5)
        with pytest.raises(HoldoutBudgetExceeded):
            measure.holdout_report(_node(), runner, inc, 0.5)
    finally:
        events.close()
    tree_src = (ROOT / "harness" / "tree.py").read_text(encoding="utf-8")
    assert not re.search(r"_holdout_visits\s*>=", tree_src)
    assert not re.search(r"holdout_visits\s*>=", tree_src)


def test_promotion_event_carries_both_deltas(tmp_path: Path):
    write(tmp_path / "fake-0001", instant=True)
    rows = [
        json.loads(line)
        for line in (tmp_path / "fake-0001" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    promoted = [
        e
        for e in rows
        if e.get("type") == "verdict" and e.get("state") == "promoted"
    ]
    assert promoted
    for ev in promoted:
        assert "delta_mean" in ev and ev["delta_mean"] is not None
        assert "oracle_delta" in ev and ev["oracle_delta"] is not None


def test_oracle_features_path_survives_env_filter():
    from dataclasses import fields

    names = {f.name for f in fields(TaskPaths)}
    assert "oracle_features" in names
    forbidden = ("holdout", "rulebook", "protocols")
    oracle = DATA_DIR / "oracle_features.csv"
    blob = str(oracle.resolve()).lower()
    for word in forbidden:
        assert word not in blob, blob


def test_holdout_runs_only_after_passing_verdict(tmp_path: Path):
    """Rejected replicate must not spend an oracle visit (#5)."""
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)
    measure = Measure(events, proto, _band(), metric="cvr_auc")
    visits_before = measure.holdout_visits

    def should_not_run():
        raise AssertionError("oracle visited before/without a passing verdict")

    results = [
        RunResult(
            node=1,
            attempt=1,
            seed=s,
            rung="full",
            ok=True,
            metrics={"cvr_auc": 0.40},
            failure_class=None,
            stderr_tail="",
            gpu_s=0.0,
            wall_s=0.1,
            result_path=None,
            checkpoint_path=None,
        )
        for s in (1, 2, 3)
    ]
    from harness.measure import SeedCache

    try:
        v = measure.verdict(
            _node(),
            results,
            SeedCache({1: 0.55, 2: 0.55, 3: 0.55}),
            "replicate",
            attribution="clear",
            on_promote_oracle=should_not_run,
        )
    finally:
        events.close()
    assert v.state == "rejected"
    assert measure.holdout_visits == visits_before


def _runner_for_env(tmp_path: Path, task: RecordingTask) -> Runner:
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)
    return Runner(
        events,
        task,
        {"paths": _paths(tmp_path), "run_dir": tmp_path / "run", "device": "cpu"},
        backend=_OkBackend(),
        heartbeat_s=60.0,
    )


def test_oracle_present_on_holdout_absent_on_screen(tmp_path: Path):
    runner = _runner_for_env(tmp_path, RecordingTask())
    paths = runner.run_cfg["paths"]
    ws = tmp_path / "ws"
    common = dict(workspace=ws, paths=paths, seed=1, overrides={}, epochs=1, max_rows=None)
    screen = runner._build_env(**common, rung="screen")
    holdout = runner._build_env(**common, rung="holdout")
    runner.events.close()
    assert "ORACLE" not in screen
    assert "ORACLE" in holdout
    assert Path(holdout["ORACLE"]).resolve() == Path(paths.oracle_features).resolve()
    assert "HOLDOUT" not in screen
    assert "HOLDOUT" not in holdout


def test_holdout_injected_env_refused(tmp_path: Path):
    runner = _runner_for_env(
        tmp_path, RecordingTask(extra_env={"HOLDOUT": str(tmp_path / "leak.csv")})
    )
    paths = runner.run_cfg["paths"]
    try:
        with pytest.raises(AssertionError):
            runner._build_env(
                workspace=tmp_path / "ws",
                paths=paths,
                seed=1,
                rung="screen",
                overrides={},
                epochs=1,
                max_rows=None,
            )
    finally:
        runner.events.close()


def test_thirteenth_promotion_omits_oracle_delta(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "run", "t11", proto)

    class FakeRunner:
        run_cfg = {"timeout_s": 5.0}

        def run(self, node, rung, seed, timeout_s, **kwargs):
            return RunResult(
                node=node.id,
                attempt=1,
                seed=seed,
                rung=rung,
                ok=True,
                metrics={"cvr_auc": 0.56},
                failure_class=None,
                stderr_tail="",
                gpu_s=0.0,
                wall_s=0.1,
                result_path=None,
                checkpoint_path=None,
            )

    measure = Measure(events, proto, _band(), metric="cvr_auc")
    from harness.measure import SeedCache

    inc = SeedCache({s: 0.55 for s in range(1, HOLDOUT_SEEDS + 1)})
    runner = FakeRunner()
    results = [
        RunResult(
            node=1,
            attempt=1,
            seed=s,
            rung="full",
            ok=True,
            metrics={"cvr_auc": 0.57},
            failure_class=None,
            stderr_tail="",
            gpu_s=0.0,
            wall_s=0.1,
            result_path=None,
            checkpoint_path=None,
        )
        for s in (1, 2, 3)
    ]
    node = _node()

    def oracle():
        return measure.holdout_report(node, runner, inc, 0.5).delta_mean

    try:
        for _ in range(13):
            v = measure.verdict(
                node, results, inc, "replicate",
                attribution="clear",
                on_promote_oracle=oracle,
            )
            assert v.state == "promoted"
    finally:
        events.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / "run" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    promoted = [
        e for e in rows if e.get("type") == "verdict" and e.get("state") == "promoted"
    ]
    assert len(promoted) == 13
    for ev in promoted[:12]:
        assert ev.get("oracle_delta") is not None
    assert "oracle_delta" not in promoted[12]
    failures = [e for e in rows if e.get("type") == "failure"]
    assert failures
    assert "oracle" in failures[-1]["summary"].lower()
