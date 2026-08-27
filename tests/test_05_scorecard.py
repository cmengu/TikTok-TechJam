"""Phase 5 slow scorecard — real runner on ~200K synthetic."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from sklearn.metrics import roc_auc_score

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.measure import METRIC, Measure, SeedCache
from harness.runner import Runner
from harness.tasks.synthetic import SyntheticTask
from harness.types import Cost, Node

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def synth_200k(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth200k-p5")
    proto = placeholder_protocol(root)
    task = SyntheticTask(n_impressions=200_000)
    paths = task.prepare(proto, root / "data")
    return task, paths, proto, root


def _node(nid: int, features_tag: str) -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id=f"h-{features_tag}",
        commit=None,
        state="running",
        rung="screen",
        kind="draft",
        scores={},
        seeds=[1],
        cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"),
        created_seq=nid,
    )


def _read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class RecordingRunner:
    def __init__(self, inner: Runner) -> None:
        self.inner = inner
        self.by_rung_seed: dict[tuple[str, int], float] = {}
        self.run_cfg = inner.run_cfg

    def run(self, *args, **kwargs):
        result = self.inner.run(*args, **kwargs)
        if result.ok and METRIC in result.metrics:
            self.by_rung_seed[(result.rung, result.seed)] = float(
                result.metrics[METRIC]
            )
        return result


def _single_feature_aucs(paths) -> dict[str, float]:
    table = pq.read_table(paths.train)
    click = np.asarray(table.column("click"))
    conv = np.asarray(table.column("conversion"))
    mask = click == 1
    out: dict[str, float] = {}
    for name in ("f_true", "f_marginal", "f_zero", "f_leak"):
        if name not in table.column_names:
            continue
        feat = np.asarray(table.column(name), dtype=np.float64)
        out[name] = float(roc_auc_score(conv[mask], feat[mask]))
    return out


@pytest.fixture(scope="module")
def scorecard(synth_200k, tmp_path_factory):
    """Calibrate once; climb the ladder for each planted feature."""
    task, paths, proto, _root = synth_200k
    run_root = tmp_path_factory.mktemp("p5-scorecard-run")
    events = EventLog(run_root, "scorecard", proto)
    run_cfg = {
        "paths": paths,
        "run_dir": run_root,
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        # 1 epoch at 200K leaves σ_full ≈ 0.03 (> SIGMA_UNSTABLE). 12 epochs
        # pins σ_full under 0.02 and keeps screen σ low enough for f_true to clear.
        "epochs": 12,
        "features": "base",
        "poll_s": 0.5,
        "timeout_s": 600.0,
        "stall_threshold_s": 300.0,
    }
    inner = Runner(events, task, run_cfg, heartbeat_s=30.0)
    runner = RecordingRunner(inner)
    measure = Measure(events, proto, band=None)
    baseline = _node(1, "base")

    band = measure.calibrate_from_runs(
        runner,
        baseline,
        screen_seeds=[1, 2, 3, 4, 5],
        full_seeds=[1, 2, 3],
        fixed_pair=[1, 1],
    )
    inc_screen = {
        s: runner.by_rung_seed[("screen", s)] for s in (1, 2, 3, 4, 5)
    }
    inc_full = {s: runner.by_rung_seed[("full", s)] for s in (1, 2, 3)}
    aucs = _single_feature_aucs(paths)

    outcomes: dict[str, str] = {}
    deltas_log: dict[str, list[float]] = {}

    def climb(nid: int, features: str, key: str) -> str:
        runner.run_cfg["features"] = features
        node = _node(nid, key)
        screen_res = runner.run(node, "screen", seed=1, timeout_s=600.0)
        assert screen_res.ok, f"{key} screen failed: {screen_res.failure_class}"
        v_screen = measure.verdict(
            node, [screen_res], SeedCache(inc_screen), "screen"
        )
        if v_screen.state != "replicating":
            outcomes[key] = v_screen.state
            deltas_log[key] = list(v_screen.delta_per_seed)
            return v_screen.state
        results = [
            runner.run(node, "full", seed=s, timeout_s=600.0) for s in (1, 2, 3)
        ]
        assert all(r.ok for r in results), f"{key} replicate run failed"
        feature_aucs = {k: v for k, v in aucs.items() if k in features}
        v_rep = measure.verdict(
            node,
            results,
            SeedCache(inc_full),
            "replicate",
            attribution="clear",
            single_feature_aucs=feature_aucs,
        )
        outcomes[key] = v_rep.state
        deltas_log[key] = list(v_rep.delta_per_seed)
        if key == "true" and v_rep.state != "promoted":
            print(
                f"TRUE_FEATURE_DEBUG deltas={v_rep.delta_per_seed} "
                f"band={band} mean={v_rep.delta_mean}"
            )
        if key == "marginal" and v_rep.state == "rejected":
            print(
                f"MARGINAL_DEBUG deltas={v_rep.delta_per_seed} "
                f"band={band} mean={v_rep.delta_mean}"
            )
        return v_rep.state

    climb(10, "base,f_zero", "zero")
    climb(20, "base,f_true", "true")
    climb(30, "base,f_marginal", "marginal")
    climb(40, "base,f_leak", "leak")

    events.close()
    log = _read_events(run_root)

    fp = 1 if outcomes["zero"] == "promoted" else 0
    fn = 1 if outcomes["true"] != "promoted" else 0
    leak_caught = outcomes["leak"] == "leaked"
    marginal = outcomes["marginal"]
    line = (
        f"FP={fp} FN={fn} marginal={marginal} "
        f"leak={'caught' if leak_caught else 'missed'}"
    )
    print(line)

    return {
        "band": band,
        "outcomes": outcomes,
        "deltas": deltas_log,
        "events": log,
        "line": line,
        "fp": fp,
        "fn": fn,
        "leak_caught": leak_caught,
    }


@pytest.mark.slow
def test_baseline_calibrates(scorecard):
    band = scorecard["band"]
    assert band.sigma_full < 0.02
    assert band.bar >= 0.010


@pytest.mark.slow
def test_zero_feature_not_promoted(scorecard):
    assert scorecard["outcomes"]["zero"] != "promoted"


@pytest.mark.slow
def test_true_feature_promoted(scorecard):
    assert scorecard["outcomes"]["true"] == "promoted", (
        f"deltas={scorecard['deltas']['true']} band={scorecard['band']}"
    )


@pytest.mark.slow
def test_marginal_feature_not_rejected(scorecard):
    state = scorecard["outcomes"]["marginal"]
    assert state in {"promoted", "inconclusive"}, (
        f"marginal rejected; deltas={scorecard['deltas']['marginal']} "
        f"band={scorecard['band']}"
    )
    print(f"marginal mean Δ={sum(scorecard['deltas']['marginal'])/3:.4f}")


@pytest.mark.slow
def test_leak_feature_trips(scorecard):
    assert scorecard["outcomes"]["leak"] == "leaked"


@pytest.mark.slow
def test_holdout_never_in_ladder(scorecard):
    holdouts = [
        e
        for e in scorecard["events"]
        if e["type"] == "measurement" and e.get("rung") == "holdout"
    ]
    assert holdouts == []


@pytest.mark.slow
def test_scorecard_printed(scorecard):
    line = scorecard["line"]
    assert re.match(
        r"FP=0 FN=0 marginal=(promoted|inconclusive) leak=caught", line
    ), line
    assert scorecard["fp"] == 0
    assert scorecard["fn"] == 0
    assert scorecard["leak_caught"] is True
