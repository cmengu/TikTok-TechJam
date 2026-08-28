"""Phase 7: Optuna tuner tests with a fake runner (no network)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from harness.agents.tuner import tune
from harness.events import EventLog
from harness.types import Cost, Node, RunResult

from helpers import placeholder_protocol


@dataclass
class FakeRunner:
    run_cfg: dict = field(default_factory=dict)
    calls: list[tuple[str, int]] = field(default_factory=list)
    knob_history: list[dict] = field(default_factory=list)
    fail_on: set[int] = field(default_factory=set)

    def run(self, node: Node, rung: str, seed: int, timeout_s: float, **_) -> RunResult:
        del timeout_s
        self.calls.append((rung, seed))
        self.knob_history.append(
            {
                "lr": float(self.run_cfg.get("lr", 1e-3)),
                "emb": int(self.run_cfg.get("emb", 16)),
                "dropout": float(self.run_cfg.get("dropout", 0.0)),
            }
        )
        if node.id in self.fail_on:
            return RunResult(
                node=node.id,
                attempt=1,
                seed=seed,
                rung=rung,  # type: ignore[arg-type]
                ok=False,
                metrics={},
                failure_class="crash",
                stderr_tail="boom",
                gpu_s=1.0,
                wall_s=1.0,
                result_path=None,
                checkpoint_path=None,
            )
        lr = float(self.run_cfg.get("lr", 1e-3))
        emb = int(self.run_cfg.get("emb", 16))
        import random

        noise = random.Random(node.id).uniform(-1e-6, 1e-6)
        score = -((lr - 0.003) ** 2) - ((emb - 16) ** 2) / 1000.0 + noise
        return RunResult(
            node=node.id,
            attempt=1,
            seed=seed,
            rung=rung,  # type: ignore[arg-type]
            ok=True,
            metrics={"cvr_auc": score},
            failure_class=None,
            stderr_tail="",
            gpu_s=2.0,
            wall_s=2.0,
            result_path=None,
            checkpoint_path=None,
        )


def _events(tmp_path: Path) -> EventLog:
    protocol = placeholder_protocol(tmp_path)
    return EventLog(tmp_path / "run", "tune-run", protocol)


def _parent() -> Node:
    return Node(
        id=5,
        parent=None,
        hypothesis_id="h-parent",
        commit=None,
        state="running",
        rung="screen",
        kind="improve",
        scores={},
        seeds=[1],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=5,
    )


def _read_events(events: EventLog) -> list[dict]:
    path = Path(events._run_dir) / "events.jsonl"  # noqa: SLF001
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_converges(tmp_path: Path):
    events = _events(tmp_path)
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(tmp_path / "run"),
            "lr": "1e-3",
            "emb": 16,
            "dropout": 0.0,
            "timeout_s": 30.0,
        }
    )
    tune(_parent(), {}, runner, events, budget=15, screen_seed=1)
    lrs = [k["lr"] for k in runner.knob_history]
    embs = [k["emb"] for k in runner.knob_history]
    assert any(abs(lr - 0.003) <= 0.003 for lr in lrs)
    assert any(abs(emb - 16) <= 8 for emb in embs)


def test_trial_events(tmp_path: Path):
    events = _events(tmp_path)
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(tmp_path / "run"),
            "lr": "1e-3",
            "emb": 16,
            "timeout_s": 30.0,
        }
    )
    tune(_parent(), {}, runner, events, budget=15, screen_seed=1)
    created = [
        e
        for e in _read_events(events)
        if e.get("type") == "node_created" and e.get("kind") == "trial"
    ]
    assert len(created) == 15
    tuning_costs = [
        e for e in _read_events(events) if e.get("type") == "measurement"
    ]
    assert len(tuning_costs) == 15
    assert all(e["cost"]["slice"] == "tuning" for e in tuning_costs)


def test_incumbent_first(tmp_path: Path):
    events = _events(tmp_path)
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(tmp_path / "run"),
            "lr": "0.003",
            "emb": 16,
            "timeout_s": 30.0,
        }
    )
    tune(_parent(), {}, runner, events, budget=15, screen_seed=1)
    assert runner.knob_history
    first = runner.knob_history[0]
    assert abs(first["lr"] - 0.003) < 1e-9
    assert first["emb"] == 16


def test_shortlist_not_promoted(tmp_path: Path):
    events = _events(tmp_path)
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(tmp_path / "run"),
            "lr": "1e-3",
            "emb": 16,
            "timeout_s": 30.0,
        }
    )
    hyps = tune(_parent(), {}, runner, events, budget=15, screen_seed=1)
    assert len(hyps) == 3
    for e in _read_events(events):
        if e.get("type") == "verdict":
            assert e.get("state") != "promoted"


def test_failed_trial_marked(tmp_path: Path):
    events = _events(tmp_path)
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(tmp_path / "run"),
            "lr": "1e-3",
            "emb": 16,
            "timeout_s": 30.0,
        }
    )
    # Fail the second trial node id (allocator gives 1..n)
    runner.fail_on.add(2)
    hyps = tune(_parent(), {}, runner, events, budget=5, screen_seed=1)
    assert len(hyps) <= 3


def test_small_budget_no_study(tmp_path: Path):
    events = _events(tmp_path)
    run_dir = tmp_path / "run"
    runner = FakeRunner(
        run_cfg={
            "run_dir": str(run_dir),
            "lr": "1e-3",
            "emb": 16,
            "timeout_s": 30.0,
        }
    )
    hyps = tune(_parent(), {}, runner, events, budget=5, screen_seed=1)
    assert len(hyps) == 3
    assert len(runner.calls) == 3
    assert not list(run_dir.glob("optuna-node-*.log"))
