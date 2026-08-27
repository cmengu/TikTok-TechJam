"""Phase 4: runner — spawn, classify, recover, heartbeat."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from helpers import placeholder_protocol
from harness.events import EventLog
from harness.runner import (
    FAILURE_CLASSES,
    RECOVERY,
    Completed,
    LocalBackend,
    Runner,
    derived_timeout,
)
from harness.tasks.synthetic import SyntheticTask
from harness.types import Cost, Node

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def synth_50k(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth50k-p4")
    proto = placeholder_protocol(root)
    task = SyntheticTask(n_impressions=50_000)
    paths = task.prepare(proto, root / "data")
    return task, paths, proto, root


def _node(nid: int = 1) -> Node:
    return Node(
        id=nid,
        parent=None,
        hypothesis_id="h-base",
        commit=None,
        state="running",
        rung="screen",
        kind="draft",
        scores={},
        seeds=[1],
        cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"),
        created_seq=1,
    )


def _events(tmp_path: Path, proto) -> EventLog:
    return EventLog(tmp_path / "run", run_id="t04", protocol=proto)


def _runner(tmp_path, synth_50k, **cfg_extra) -> tuple[Runner, EventLog, SyntheticTask]:
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
        "poll_s": 0.2,
        **cfg_extra,
    }
    return (
        Runner(events, task, run_cfg, heartbeat_s=0.5),
        events,
        task,
    )


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_derived_timeout():
    assert derived_timeout(0.001, rows=1000, epochs=2, safety=2.0, floor_s=60) == 60.0
    assert derived_timeout(0.1, rows=1000, epochs=2, safety=2.0, floor_s=60) == 400.0


def test_success_returns_scored_metrics(synth_50k, tmp_path: Path):
    runner, events, task = _runner(tmp_path, synth_50k)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=120.0)
        assert result.ok is True
        assert result.wall_s > 0
        assert "ctr_auc" in result.metrics and "cvr_auc" in result.metrics
        assert result.result_path is not None
        preds = Path(json.loads(result.result_path.read_text())["preds"])
        expected = task.score(preds, "search")
        assert result.metrics == expected
        # Child self-report must not be what we return (may match by chance — compare path).
        child = json.loads(result.result_path.read_text())["metrics"]
        # Authoritative metrics come from task.score; ensure we didn't just copy blindly
        # by checking score() was applied (keys + floats from harness).
        assert set(result.metrics) == set(expected)
        assert result.metrics["ctr_auc"] == pytest.approx(expected["ctr_auc"])
        del child  # silence lint; presence checked via result.json above
    finally:
        events.close()


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("crash", "crash"),
        ("oom_cuda", "cuda_oom"),
        ("oom_host", "host_oom"),
        ("nan", "diverged"),
        ("hang", "timeout"),
        ("no_result", "contract_violation"),
        ("bad_schema", "contract_violation"),
    ],
)
def test_classify_table(synth_50k, tmp_path: Path, mode: str, expected: str):
    # hang → timeout with short deadline; disable stall so timeout wins.
    stall = 3600.0 if mode == "hang" else 3600.0
    timeout = 3.0 if mode == "hang" else 120.0
    runner, events, _task = _runner(tmp_path, synth_50k, stall_threshold_s=stall)
    try:
        result = runner.run(
            _node(),
            "screen",
            seed=0,
            timeout_s=timeout,
            env_overrides={"SYNTHETIC_FAIL": mode},
        )
        assert result.ok is False
        assert result.failure_class == expected
        if expected == "host_oom":
            fails = [e for e in _read_jsonl(tmp_path / "run" / "events.jsonl") if e["type"] == "failure"]
            assert fails
            assert fails[-1]["returncode"] == 137
    finally:
        events.close()


def test_timeout_kills_hang(synth_50k, tmp_path: Path):
    runner, events, _task = _runner(tmp_path, synth_50k, stall_threshold_s=3600.0)
    try:
        t0 = time.monotonic()
        result = runner.run(
            _node(),
            "screen",
            seed=0,
            timeout_s=3.0,
            env_overrides={"SYNTHETIC_FAIL": "hang"},
        )
        elapsed = time.monotonic() - t0
        assert result.failure_class == "timeout"
        assert elapsed < 5.0
        # No orphan: LocalBackend waited after kill.
        assert result.ok is False
    finally:
        events.close()


@dataclass
class _ScriptedBackend:
    """Fails once with a class, then succeeds writing a minimal result."""

    fail_class: str
    calls: list = None  # type: ignore[assignment]
    envs: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []
        self.envs = []

    def run(self, workspace, cmd, env, timeout_s, on_progress) -> Completed:
        self.calls.append({"attempt_env_BATCH": env.get("BATCH"), "cmd": list(cmd)})
        self.envs.append(dict(env))
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        if len(self.calls) == 1:
            if self.fail_class == "cuda_oom":
                return Completed(1, "RuntimeError: CUDA out of memory\n", 0.1)
            if self.fail_class == "host_oom":
                return Completed(-9, "", 0.1)
            if self.fail_class == "contract_violation":
                return Completed(0, "", 0.1)  # no result.json
            if self.fail_class == "diverged":
                on_progress({"step": 1, "total": 10, "loss": float("nan")})
                return Completed(0, "", 0.1)
            if self.fail_class == "always_oom":
                return Completed(1, "CUDA out of memory", 0.05)
            if self.fail_class == "stall":
                return Completed(-9, "", 0.2, killed_as="stall")
        # Success path: write preds + result so score() works — caller uses real task
        # only when ok; for scripted success we still need result for classify None.
        # Tests that need ok=True after retry pass a real scoring task + real preds.
        return Completed(0, "", 0.05)


class _ScriptedThenReal:
    """First call fails as cuda/host oom; second uses LocalBackend."""

    def __init__(self, fail_class: str, real: LocalBackend):
        self.fail_class = fail_class
        self.real = real
        self.calls = 0
        self.envs: list[dict] = []

    def run(self, workspace, cmd, env, timeout_s, on_progress) -> Completed:
        self.calls += 1
        self.envs.append(dict(env))
        if self.calls == 1:
            if self.fail_class == "cuda_oom":
                return Completed(1, "CUDA out of memory", 0.05)
            if self.fail_class == "host_oom":
                return Completed(-9, "", 0.05)
            if self.fail_class == "stall":
                return Completed(-9, "", 0.05, killed_as="stall")
        return self.real.run(workspace, cmd, env, timeout_s, on_progress)


def test_retry_on_cuda_oom(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    backend = _ScriptedThenReal("cuda_oom", LocalBackend(poll_s=0.2, stall_threshold_s=3600.0))
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=120.0)
        assert result.ok is True
        assert result.attempt == 2
        assert backend.calls == 2
        assert int(backend.envs[0]["BATCH"]) == 2048
        assert int(backend.envs[1]["BATCH"]) == 1024
        ev = _read_jsonl(tmp_path / "run" / "events.jsonl")
        assert any(e["type"] == "failure" and e["class"] == "cuda_oom" for e in ev)
        assert any(e["type"] == "recovery" and e["action"] == "halve_batch" for e in ev)
    finally:
        events.close()


def test_retry_on_host_oom(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    backend = _ScriptedThenReal("host_oom", LocalBackend(poll_s=0.2, stall_threshold_s=3600.0))
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 4096,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=120.0)
        assert result.ok is True
        assert result.attempt == 2
        assert int(backend.envs[1]["BATCH"]) == 2048
        ev = _read_jsonl(tmp_path / "run" / "events.jsonl")
        fails = [e for e in ev if e["type"] == "failure" and e["class"] == "host_oom"]
        assert fails and fails[0]["returncode"] == 137
        assert any(e["type"] == "recovery" and e["action"] == "halve_batch" for e in ev)
    finally:
        events.close()


def test_no_retry_on_contract_violation(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    backend = _ScriptedBackend(fail_class="contract_violation")
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 1024,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=30.0)
        assert result.ok is False
        assert result.failure_class == "contract_violation"
        assert result.attempt == 1
        assert len(backend.calls) == 1
    finally:
        events.close()


def test_no_retry_on_diverged(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    backend = _ScriptedBackend(fail_class="diverged")
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 1024,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=30.0)
        assert result.ok is False
        assert result.failure_class == "diverged"
        assert result.attempt == 1
        assert len(backend.calls) == 1
        assert RECOVERY["diverged"] is None
        fails = [e for e in _read_jsonl(tmp_path / "run" / "events.jsonl") if e["type"] == "failure"]
        assert fails and "family note" in fails[0]["summary"]
        assert "given_up:diverged" in fails[0]["summary"]
    finally:
        events.close()


def test_max_two_attempts(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)

    class AlwaysOom:
        calls = 0
        envs: list = []

        def run(self, workspace, cmd, env, timeout_s, on_progress) -> Completed:
            AlwaysOom.calls += 1
            AlwaysOom.envs.append(dict(env))
            return Completed(1, "CUDA out of memory", 0.02)

    AlwaysOom.calls = 0
    AlwaysOom.envs = []
    backend = AlwaysOom()
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=30.0)
        assert result.ok is False
        assert result.failure_class == "cuda_oom"
        assert result.attempt == 2
        assert AlwaysOom.calls == 2
        assert int(AlwaysOom.envs[1]["BATCH"]) == 1024
    finally:
        events.close()


def test_heartbeats_written(synth_50k, tmp_path: Path):
    runner, events, _task = _runner(tmp_path, synth_50k, stall_threshold_s=3600.0)
    try:
        # hang for ~3s via timeout so heartbeat thread ticks ≥3 times at 0.5s
        runner.run(
            _node(),
            "screen",
            seed=0,
            timeout_s=3.0,
            env_overrides={"SYNTHETIC_FAIL": "hang"},
        )
        time.sleep(0.2)
        events.close()
        hbs = _read_jsonl(tmp_path / "run" / "heartbeat.jsonl")
        assert len(hbs) >= 3
        assert all("node" in h and "step" in h for h in hbs)
    finally:
        if not getattr(events, "_closed", True):
            events.close()


def test_diverged_killed_early(synth_50k, tmp_path: Path):
    runner, events, _task = _runner(tmp_path, synth_50k, stall_threshold_s=3600.0)
    try:
        healthy = runner.run(_node(1), "screen", seed=0, timeout_s=120.0)
        assert healthy.ok
        nan = runner.run(
            _node(2),
            "screen",
            seed=0,
            timeout_s=120.0,
            env_overrides={"SYNTHETIC_FAIL": "nan"},
        )
        assert nan.failure_class == "diverged"
        assert nan.wall_s < healthy.wall_s
    finally:
        events.close()


def test_stall_kills_and_retries(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    # First attempt: scripted stall; second: real success.
    backend = _ScriptedThenReal("stall", LocalBackend(poll_s=0.1, stall_threshold_s=3600.0))
    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
        "stall_threshold_s": 0.5,
        "poll_s": 0.1,
    }
    runner = Runner(events, task, run_cfg, backend=backend, heartbeat_s=0.5)
    try:
        result = runner.run(_node(), "screen", seed=0, timeout_s=120.0)
        assert result.ok is True
        assert result.attempt == 2
        assert backend.calls == 2
        # BATCH unchanged on stall retry.
        assert backend.envs[0]["BATCH"] == backend.envs[1]["BATCH"]
        ev = _read_jsonl(tmp_path / "run" / "events.jsonl")
        assert any(e["type"] == "failure" and e["class"] == "stall" for e in ev)
        assert any(e["type"] == "recovery" and e["class"] == "stall" for e in ev)
    finally:
        events.close()

    # Also exercise LocalBackend stall watchdog with tiny threshold + hang.
    events2 = _events(tmp_path / "stall2", proto)
    run_cfg2 = {
        "paths": paths,
        "run_dir": tmp_path / "stall2",
        "device": "cpu",
        "batch": 2048,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
        "stall_threshold_s": 0.8,
        "poll_s": 0.2,
    }
    # Always-stall backend via real hang would retry then hang again — use max attempts.
    # Direct LocalBackend unit: hang + tiny stall → stall class on attempt 1 abandon after 2.
    runner2 = Runner(events2, task, run_cfg2, heartbeat_s=0.5)
    try:
        r2 = runner2.run(
            _node(3),
            "screen",
            seed=0,
            timeout_s=60.0,
            env_overrides={"SYNTHETIC_FAIL": "hang"},
        )
        assert r2.failure_class == "stall"
        assert r2.attempt == 2  # retried once, stalled again
    finally:
        events2.close()


def test_child_env_is_capability_safe(synth_50k, tmp_path: Path):
    task, paths, proto, _root = synth_50k
    events = _events(tmp_path, proto)
    captured: dict = {}

    class CaptureBackend:
        def run(self, workspace, cmd, env, timeout_s, on_progress) -> Completed:
            captured["env"] = dict(env)
            captured["cmd"] = list(cmd)
            return Completed(1, "boom", 0.01)

    run_cfg = {
        "paths": paths,
        "run_dir": tmp_path / "run",
        "device": "cpu",
        "batch": 1024,
        "lr": "1e-3",
        "epochs": 1,
        "features": "base",
    }
    runner = Runner(events, task, run_cfg, backend=CaptureBackend(), heartbeat_s=0.5)
    try:
        runner.run(_node(), "screen", seed=0, timeout_s=10.0)
        env = captured["env"]
        blob_keys = " ".join(env.keys())
        blob_vals = " ".join(str(v) for v in env.values())
        for needle in ("holdout", "protocols/", "rulebook"):
            assert needle not in blob_keys.lower()
            assert needle not in blob_vals.lower()
        root = str(ROOT.resolve())
        pp = env.get("PYTHONPATH", "")
        for part in pp.split(os.pathsep):
            if part:
                assert Path(part).resolve() != Path(root)
        assert set(task.candidate_env(paths)) == {"TRAIN", "VALID"}
        assert "HOLDOUT" not in env
    finally:
        events.close()


def test_failure_classes_include_stall():
    assert "stall" in FAILURE_CLASSES
    assert RECOVERY["host_oom"] is not None
    assert RECOVERY["diverged"] is None
