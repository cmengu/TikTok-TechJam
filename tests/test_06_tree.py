"""Phase 6: tree / queue / workspace unit tests (fake runner + fake measure)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.measure import Band, SeedCache
from harness.tree import (
    FULL_SEEDS,
    SCREEN_SEED,
    IllegalTransition,
    PatchCoder,
    Queue,
    Tree,
    Workspace,
    family_stats,
    rebuild,
    transition,
)
from harness.types import EVENT_TYPES, STATES, Cost, Hypothesis, Node, RunResult, Verdict

ROOT = Path(__file__).resolve().parents[1]


def _read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _band() -> Band:
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


def _hyp(
    hid: str,
    *,
    stage: str = "features",
    mechanism: str = "m",
    description: str | None = None,
    gain: float = 0.01,
    patch: Path | None = None,
    parent: int | None = None,
) -> Hypothesis:
    return Hypothesis(
        id=hid,
        stage=stage,  # type: ignore[arg-type]
        mechanism=mechanism,
        description=description or f"hyp {hid}",
        citation="no prior",
        expected_gain=gain,
        expected_gpu_h=0.1,
        parent_node=parent,
        patch=patch,
    )


def _node(nid: int = 1, state: str = "screening", kind: str = "improve") -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id=f"h-{nid}",
        commit=None,
        state=state,  # type: ignore[arg-type]
        rung="screen",
        kind=kind,  # type: ignore[arg-type]
        scores={},
        seeds=[],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=nid,
    )


@dataclass
class FakeRunner:
    """Returns canned RunResults; records (rung, seed) calls."""

    scores: dict[tuple[str, int], float] = field(default_factory=dict)
    fail_on: set[tuple[str, int]] = field(default_factory=set)
    fail_class: str = "crash"
    calls: list[tuple[str, int]] = field(default_factory=list)
    run_cfg: dict = field(default_factory=lambda: {"timeout_s": 60.0})
    events: EventLog | None = None

    def run(self, node, rung, seed, timeout_s, **kwargs):  # noqa: ANN001
        del timeout_s
        attempt = int(kwargs.get("attempt", 1))
        self.calls.append((str(rung), int(seed)))
        key = (str(rung), int(seed))
        if key in self.fail_on:
            if self.events is not None:
                self.events.emit("failure", node=node.id, attempt=attempt, stderr_tail="boom", returncode=1, summary=f"node {node.id} {self.fail_class}", **{"class": self.fail_class})
            return RunResult(
                node=node.id,
                attempt=1,
                seed=int(seed),
                rung=rung,
                ok=False,
                metrics={},
                failure_class=self.fail_class,
                stderr_tail="boom",
                gpu_s=0.0,
                wall_s=1.0,
                result_path=None,
                checkpoint_path=None,
            )
        score = float(self.scores.get(key, 0.55))
        return RunResult(
            node=node.id,
            attempt=1,
            seed=int(seed),
            rung=rung,
            ok=True,
            metrics={"cvr_auc": score},
            failure_class=None,
            stderr_tail="",
            gpu_s=0.0,
            wall_s=6.0,
            result_path=None,
            checkpoint_path=None,
        )


@dataclass
class FakeMeasure:
    """Scripted verdicts by call order; records holdout_report calls."""

    script: list[Verdict] = field(default_factory=list)
    band: Band | None = field(default_factory=_band)
    holdout_calls: list[int] = field(default_factory=list)
    metric: str = "cvr_auc"
    _i: int = 0
    _holdout_visits: int = 0
    events: EventLog | None = None

    @property
    def holdout_visits(self) -> int:
        return self._holdout_visits

    def calibrate_from_runs(self, *a, **k):  # noqa: ANN001
        del a, k
        return self.band

    def verdict(self, node, results, incumbent, rung, attribution=None, **k):  # noqa: ANN001
        del incumbent, k
        if self._i >= len(self.script):
            raise RuntimeError("FakeMeasure script exhausted")
        v = self.script[self._i]
        self._i += 1
        v = replace(v, node=node.id, rung=rung)
        assert self.events is not None
        self.events.emit(
            "verdict",
            node=node.id,
            state=v.state,
            metric=v.metric,
            scores=[float(r.metrics.get("cvr_auc", 0.0)) for r in results],
            seeds=[r.seed for r in results],
            band={"bar": 0.01},
            rung=rung,
            delta_mean=v.delta_mean,
            delta_per_seed=v.delta_per_seed,
            attribution=attribution,
            gpu_min=0.1,
            producer="measure",
            summary=v.reason,
        )
        if v.state == "promoted":
            self.events.emit(
                "incumbent_changed",
                node=node.id,
                reason="promotion",
                summary=f"node {node.id} became incumbent (promotion)",
            )
        return v

    def holdout_report(self, node, runner, incumbent, best_reported):  # noqa: ANN001
        del runner, incumbent
        self._holdout_visits += 1
        self.holdout_calls.append(node.id)
        assert self.events is not None
        self.events.emit(
            "measurement",
            node=node.id,
            rung="holdout",
            visit=self._holdout_visits,
            metric="cvr_auc",
            value=best_reported,
            producer="measure",
            summary=f"holdout visit={self._holdout_visits}",
        )
        from harness.measure import HoldoutReport

        return HoldoutReport(
            visit=self._holdout_visits,
            seeds=[1, 2, 3],
            candidate_scores=[0.5, 0.5, 0.5],
            incumbent_scores=[0.5, 0.5, 0.5],
            delta_mean=0.0,
            accepted=False,
            best_reported=best_reported,
        )

    def maybe_refresh(self):
        return None


def _verdict(state: str, rung: str = "screen", delta: float = 0.02) -> Verdict:
    return Verdict(
        node=0,
        rung=rung,  # type: ignore[arg-type]
        state=state,  # type: ignore[arg-type]
        metric="cvr_auc",
        delta_mean=delta,
        delta_per_seed=[delta],
        band=(-0.01, 0.01),
        reason=f"{rung} → {state}",
        rule_trips=[],
    )


def test_illegal_transition_raises():
    n = _node(state="rejected")
    with pytest.raises(IllegalTransition):
        transition(n, "running")
    n2 = _node(state="screening")
    transition(n2, "running")
    assert n2.state == "running"


def test_queue_order_by_score(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "q", "q", proto)
    try:
        q = Queue(events)
        # Three families; stats will rank C > B > A
        for hid, mech, gain in (
            ("a", "fam_a", 0.01),
            ("b", "fam_b", 0.02),
            ("c", "fam_c", 0.03),
        ):
            q.push(_hyp(hid, mechanism=mech, gain=gain))
        stats = {
            "features/fam_a": {
                "mean_delta": 0.01,
                "sd_delta": 0.0,
                "n": 2,
                "mean_gpu_min": 1.0,
            },
            "features/fam_b": {
                "mean_delta": 0.05,
                "sd_delta": 0.0,
                "n": 2,
                "mean_gpu_min": 1.0,
            },
            "features/fam_c": {
                "mean_delta": 0.10,
                "sd_delta": 0.0,
                "n": 2,
                "mean_gpu_min": 1.0,
            },
        }
        order = q.rerank(stats)
        assert order == ["c", "b", "a"]
    finally:
        events.close()


def test_rerank_after_rejection(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "rr", "rr", proto)
    q = Queue(events)
    q.push(_hyp("x", mechanism="fx"))
    q.push(_hyp("y", mechanism="fy"))
    events.emit(
        "node_created",
        id=1,
        parent=None,
        kind="improve",
        hypothesis_id="x",
        summary="n1",
    )
    events.emit(
        "verdict",
        node=1,
        state="rejected",
        delta_mean=-0.05,
        gpu_min=1.0,
        producer="measure",
        summary="rej",
    )
    events.emit(
        "node_created",
        id=2,
        parent=None,
        kind="improve",
        hypothesis_id="y",
        summary="n2",
    )
    events.emit(
        "verdict",
        node=2,
        state="promoted",
        delta_mean=0.05,
        gpu_min=1.0,
        producer="measure",
        summary="ok",
    )
    events.close()
    stats = family_stats(_read_events(tmp_path / "rr"))
    events2 = EventLog(tmp_path / "rr2", "rr2", proto)
    try:
        q2 = Queue(events2)
        q2.push(_hyp("x", mechanism="fx"))
        q2.push(_hyp("y", mechanism="fy"))
        order = q2.rerank(stats)
        assert order[0] == "y"
    finally:
        events2.close()
    assert any(
        e["type"] == "queue_reordered" for e in _read_events(tmp_path / "rr2")
    )


def test_dedupe(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    events = EventLog(tmp_path / "dd", "dd", proto)
    try:
        q = Queue(events)
        assert q.push(_hyp("a", description="Add F_true Feature")) is True
        assert q.push(_hyp("b", description="  add f_true feature ")) is False
        assert len(q) == 1
    finally:
        events.close()
    rows = _read_events(tmp_path / "dd")
    trips = [e for e in rows if e["type"] == "rule_trip" and e.get("rule") == "duplicate"]
    assert len(trips) == 1


def _make_tree(tmp_path: Path, measure: FakeMeasure, runner: FakeRunner, hyps: list[Hypothesis]):
    proto = placeholder_protocol(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    events = EventLog(run_dir, "t", proto)
    measure.events = events
    runner.events = events
    ws = Workspace(run_dir, "t")
    # Ensure patches exist as empty files when missing
    for h in hyps:
        if h.patch is None:
            p = run_dir / f"{h.id}.diff"
            p.write_text("", encoding="utf-8")
            h = replace(h, patch=p) if False else h
    queue = Queue(events)
    hyp_index = {}
    for h in hyps:
        if h.patch is None:
            p = ROOT / "hypotheses" / "patches" / "base.diff"
            h = Hypothesis(
                id=h.id,
                stage=h.stage,
                mechanism=h.mechanism,
                description=h.description,
                citation=h.citation,
                expected_gain=h.expected_gain,
                expected_gpu_h=h.expected_gpu_h,
                parent_node=h.parent_node,
                patch=p,
            )
        hyp_index[h.id] = h
        queue.push(h)
    tree = Tree(
        events,
        proto,
        task=None,
        runner=runner,
        measure=measure,
        coder=PatchCoder(),
        queue=queue,
        max_nodes=50,
        budget=None,
        workspace=ws,
        hyp_index=hyp_index,
        smoke_timeout_s=1.0,
        screen_timeout_s=1.0,
        full_timeout_s=1.0,
    )
    bid = events.new_node(None)
    baseline = _node(bid, state="promoted", kind="draft")
    baseline.hypothesis_id = "baseline"
    baseline.commit = ws.head()
    tree.incumbent = baseline
    tree.nodes[bid] = baseline
    tree._initial_commit = ws.head()
    tree.screen_inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50, 4: 0.50, 5: 0.50})
    tree.full_inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    tree.holdout_inc = SeedCache({1: 0.50, 2: 0.50, 3: 0.50})
    return tree, events, run_dir, ws


def test_ladder_progression(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating", "screen", 0.03),
            _verdict("promoted", "replicate", 0.03),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", SCREEN_SEED): 0.5,
            ("screen", SCREEN_SEED): 0.53,
            **{("full", s): 0.53 for s in FULL_SEEDS},
        }
    )
    tree, events, run_dir, _ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", mechanism="true", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        assert tree.step() is True
        full_calls = [c for c in runner.calls if c[0] == "full"]
        assert [s for _, s in full_calls] == list(FULL_SEEDS)
        holdout_runs = [c for c in runner.calls if c[0] == "holdout"]
        assert holdout_runs == []  # holdout via measure.holdout_report only
        rows = _read_events(run_dir)
        reps = [e for e in rows if e["type"] == "verdict" and e.get("rung") == "replicate"]
        assert len(reps) == 1
    finally:
        events.close()


def test_seed_cache_rolls_on_promotion(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating", "screen"),
            _verdict("promoted", "replicate"),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.56,
            ("full", 1): 0.57,
            ("full", 2): 0.58,
            ("full", 3): 0.59,
        }
    )
    tree, events, _run_dir, _ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        tree.step()
        assert tree.full_inc.as_dict() == {1: 0.57, 2: 0.58, 3: 0.59}
    finally:
        events.close()


def test_holdout_twice_per_run(tmp_path: Path):
    # Two promotions then a third — holdout only at first promotion + run end.
    measure = FakeMeasure(
        script=[
            _verdict("replicating"),
            _verdict("promoted", "replicate"),
            _verdict("replicating"),
            _verdict("promoted", "replicate"),
            _verdict("replicating"),
            _verdict("promoted", "replicate"),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.56,
            ("full", 1): 0.57,
            ("full", 2): 0.57,
            ("full", 3): 0.57,
        }
    )
    hyps = [
        _hyp(f"h{i}", mechanism=f"m{i}", patch=ROOT / "hypotheses/patches/f_true.diff")
        for i in range(3)
    ]
    tree, events, _run_dir, _ws = _make_tree(tmp_path, measure, runner, hyps)
    try:
        while tree.step():
            pass
        assert measure.holdout_calls  # at least first + end
        assert len(measure.holdout_calls) == 2
    finally:
        events.close()


def test_greedy_revert(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating"),
            _verdict("inconclusive", "replicate"),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.52,
            ("full", 1): 0.51,
            ("full", 2): 0.51,
            ("full", 3): 0.51,
        }
    )
    tree, events, _run_dir, ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        inc_commit = tree.incumbent.commit
        assert inc_commit
        tree.step()
        assert ws.head() == inc_commit
    finally:
        events.close()


def test_fork_on_stall(tmp_path: Path):
    # 4 improve nodes non-promoted → fork drafts; 3 → none.
    def run_n(n: int, run_name: str) -> tuple[list[dict], Tree]:
        script = []
        for _ in range(n):
            script.append(_verdict("rejected", "screen", -0.02))
        measure = FakeMeasure(script=script)
        runner = FakeRunner(scores={("smoke", 1): 0.5, ("screen", 1): 0.40})
        hyps = [
            _hyp(
                f"imp-{i}",
                mechanism=f"fam{i}",
                patch=ROOT / "hypotheses/patches/base.diff",
            )
            for i in range(n)
        ]
        extras = [
            _hyp(
                f"extra-{i}",
                mechanism=f"other{i}",
                patch=ROOT / "hypotheses/patches/f_zero.diff",
                gain=0.2,
            )
            for i in range(2)
        ]
        sub = tmp_path / run_name
        sub.mkdir(parents=True, exist_ok=True)
        tree, events, run_dir, _ws = _make_tree(sub, measure, runner, hyps)
        for e in extras:
            tree.hyp_index[e.id] = e
        try:
            for _ in range(n):
                tree.step()
        finally:
            events.close()
        return _read_events(run_dir), tree

    _rows3, tree3 = run_n(3, "stall3")
    forked3 = [n for n in tree3.nodes.values() if n.kind == "draft" and str(n.hypothesis_id).startswith("extra-")]
    assert forked3 == []

    _rows4, tree4 = run_n(4, "stall4")
    forked4 = [n for n in tree4.nodes.values() if n.kind == "draft" and str(n.hypothesis_id).startswith("extra-")]
    assert len(forked4) == 2


def test_max_live_branches(tmp_path: Path):
    measure = FakeMeasure(script=[_verdict("replicating")] * 10 + [_verdict("promoted", "replicate")] * 10)
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.55,
            ("full", 1): 0.55,
            ("full", 2): 0.55,
            ("full", 3): 0.55,
        }
    )
    tree, events, _run_dir, _ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp(f"h{i}", mechanism=f"m{i}", patch=ROOT / "hypotheses/patches/base.diff") for i in range(5)],
    )
    try:
        for i in range(2, 5):
            tree.nodes[i] = _node(i, state="running")
        assert tree._live_count() == 3
        assert tree.step() is False
    finally:
        events.close()


def test_debug_depth(tmp_path: Path):
    """Three debug retries on the same node; the fourth crash retires."""
    measure = FakeMeasure(script=[])
    runner = FakeRunner(scores={("smoke", 1): 0.5}, fail_on={("smoke", 1)}, fail_class="crash")
    tree, events, run_dir, _ws = _make_tree(tmp_path, measure, runner, [_hyp("d0", patch=ROOT / "hypotheses/patches/base.diff")])
    try:
        tree.step()
        node = max(tree.nodes.values(), key=lambda n: n.id)
        assert node.state == "retired"
        assert tree._debug_depth.get(node.id) == 3
        failures = [e for e in _read_events(run_dir) if e["type"] == "failure"]
        assert len(failures) == 4
        queued = [e for e in _read_events(run_dir) if e["type"] == "hypothesis_queued"]
        assert len(queued) == 1 and queued[0]["id"] == "d0"
    finally:
        events.close()


def test_child_builds_on_incumbent(tmp_path: Path):
    """Child hypotheses with parent_node checkout the incumbent commit."""
    measure = FakeMeasure(script=[_verdict("replicating"), _verdict("promoted", "replicate"), _verdict("rejected", "screen", -0.01)])
    runner = FakeRunner(scores={("smoke", 1): 0.5, ("screen", 1): 0.56, ("full", 1): 0.57, ("full", 2): 0.57, ("full", 3): 0.57})
    h1 = _hyp("h1", mechanism="true", patch=ROOT / "hypotheses/patches/f_true.diff")
    tree, events, _run_dir, ws = _make_tree(tmp_path, measure, runner, [h1])
    checkouts: list[str] = []
    orig = ws.checkout
    def track(commit: str) -> None:
        checkouts.append(commit)
        orig(commit)
    ws.checkout = track  # type: ignore[method-assign]
    try:
        assert tree.step() is True
        inc_commit = tree.incumbent.commit
        assert inc_commit is not None
        child_patch = tmp_path / "child.diff"
        child_patch.write_text("", encoding="utf-8")
        h2 = _hyp("h2", mechanism="child", patch=child_patch, parent=tree.incumbent.id)
        tree.hyp_index[h2.id] = h2
        tree.queue.push(h2)
        checkouts.clear()
        assert tree.step() is True
        assert inc_commit in checkouts
        assert checkouts[0] == inc_commit
    finally:
        events.close()


def test_git_per_node(tmp_path: Path):
    measure = FakeMeasure(
        script=[_verdict("rejected", "screen", -0.01)]
    )
    runner = FakeRunner(scores={("smoke", 1): 0.5, ("screen", 1): 0.4})
    tree, events, run_dir, ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        tree.step()
        node = max(tree.nodes.values(), key=lambda n: n.id)
        assert node.commit
        patch = run_dir / "patches" / f"node-{node.id:03d}.diff"
        assert patch.is_file()
        live = subprocess_diff(ws, f"{node.commit}~1..{node.commit}")
        assert patch.read_text(encoding="utf-8") == live
    finally:
        events.close()


def subprocess_rev(ws: Workspace, rev: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=str(ws.path),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def subprocess_diff(ws: Workspace, spec: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "diff", spec],
        cwd=str(ws.path),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_lessons_appended(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating"),
            _verdict("rejected", "replicate", -0.01),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.55,
            ("full", 1): 0.51,
            ("full", 2): 0.51,
            ("full", 3): 0.51,
        }
    )
    tree, events, run_dir, _ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        tree.step()
        lines = (run_dir / "lessons.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            row = json.loads(line)
            assert {"node", "family", "delta", "gpu_min", "diff_summary"} <= set(row)
    finally:
        events.close()


def test_loop_emits_only_vocab(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating"),
            _verdict("promoted", "replicate"),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.56,
            ("full", 1): 0.57,
            ("full", 2): 0.57,
            ("full", 3): 0.57,
        }
    )
    tree, events, run_dir, _ws = _make_tree(
        tmp_path,
        measure,
        runner,
        [_hyp("h1", patch=ROOT / "hypotheses/patches/f_true.diff")],
    )
    try:
        tree.run()
        for e in _read_events(run_dir):
            assert e["type"] in EVENT_TYPES
            if "state" in e and e["type"] in ("state_changed", "verdict"):
                assert e["state"] in STATES
    finally:
        events.close()


def test_rebuild_matches_live(tmp_path: Path):
    measure = FakeMeasure(
        script=[
            _verdict("replicating"),
            _verdict("promoted", "replicate"),
            _verdict("rejected", "screen", -0.02),
        ]
    )
    runner = FakeRunner(
        scores={
            ("smoke", 1): 0.5,
            ("screen", 1): 0.56,
            ("full", 1): 0.57,
            ("full", 2): 0.57,
            ("full", 3): 0.57,
        }
    )
    hyps = [
        _hyp("h-true", mechanism="planted_true", patch=ROOT / "hypotheses/patches/f_true.diff"),
        _hyp("h-zero", mechanism="planted_zero", patch=ROOT / "hypotheses/patches/f_zero.diff"),
    ]
    tree, events, run_dir, _ws = _make_tree(tmp_path, measure, runner, hyps)
    try:
        tree.run()
        live_nodes = {
            nid: {"id": n.id, "hypothesis_id": n.hypothesis_id, "state": n.state, "kind": n.kind}
            for nid, n in tree.nodes.items()
        }
        live_inc = tree.incumbent.id if tree.incumbent else None
        folded = rebuild(_read_events(run_dir))
        assert folded.incumbent_id == live_inc
        for nid, meta in folded.nodes.items():
            if nid not in live_nodes:
                continue
            assert meta["hypothesis_id"] == live_nodes[nid]["hypothesis_id"]
            assert meta["state"] == live_nodes[nid]["state"]
    finally:
        events.close()
