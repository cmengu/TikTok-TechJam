"""Phase 4: spawn candidate, timeout, classify failure, recover."""

from __future__ import annotations

import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Protocol

from harness.events import EventLog
from harness.tasks.base import Task, TaskPaths
from harness.types import Node, Rung, RunResult

FAILURE_CLASSES = (
    "cuda_oom",
    "host_oom",
    "diverged",
    "timeout",
    "contract_violation",
    "crash",
    "stall",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = REPO_ROOT / "candidate"


def _halve_batch(env: dict) -> dict:
    batch = max(1, int(env.get("BATCH", "1")) // 2)
    return {**env, "BATCH": str(batch)}


def _unchanged(env: dict) -> dict:
    return dict(env)


# None = abandon / no runner retry. Callables rewrite env for attempt 2.
RECOVERY: dict[str, Callable[[dict], dict] | None] = {
    "cuda_oom": _halve_batch,
    "host_oom": _halve_batch,  # same knob; template has no DataLoader / LOADER_WORKERS
    "diverged": None,  # abandon; family note in failure summary
    "timeout": None,
    "contract_violation": None,
    "crash": None,
    "stall": _unchanged,  # retry once, no knob change
}

RECOVERY_ACTION = {
    "cuda_oom": "halve_batch",
    "host_oom": "halve_batch",
    "stall": "retry",
}

DEFAULT_STALL_S = 5 * 60.0
SMOKE_MAX_ROWS = 20_000


@dataclass(frozen=True)
class RungSpec:
    score_split: Literal["search", "holdout"] | None
    epochs: int | None
    max_rows: int | None


RUNG_ENV: dict[Rung, RungSpec] = {
    "smoke": RungSpec(score_split=None, epochs=1, max_rows=SMOKE_MAX_ROWS),
    "screen": RungSpec(score_split="search", epochs=1, max_rows=None),
    "full": RungSpec(score_split="search", epochs=None, max_rows=None),
    "replicate": RungSpec(score_split="search", epochs=None, max_rows=None),
    "holdout": RungSpec(score_split="holdout", epochs=None, max_rows=None),
}


@dataclass
class Completed:
    returncode: int
    stderr_tail: str
    wall_s: float
    killed_as: str | None = None  # "timeout" | "stall"


class Backend(Protocol):
    def run(
        self,
        workspace: Path,
        cmd: list[str],
        env: dict,
        timeout_s: float,
        on_progress: Callable[[dict], None],
    ) -> Completed:
        ...


def _is_bad_loss(loss: float, first_loss: float | None) -> bool:
    if math.isnan(loss) or math.isinf(loss):
        return True
    if first_loss is None:
        return False
    if first_loss > 0 and loss > 10.0 * first_loss:
        return True
    return False


def progress_diverged(progress: list[dict]) -> bool:
    first: float | None = None
    for row in progress:
        raw = row.get("loss")
        if raw is None:
            continue
        loss = float(raw)
        if first is None:
            if math.isnan(loss) or math.isinf(loss):
                return True
            first = loss
            continue
        if _is_bad_loss(loss, first):
            return True
    return False


def _result_valid(result_path: Path | None) -> bool:
    """Contract: result.json exists and points at a real preds file. Metrics are harness-owned."""
    if result_path is None or not result_path.is_file():
        return False
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    preds = data.get("preds")
    if not preds:
        return False
    return Path(str(preds)).is_file()


def derived_timeout(
    seconds_per_row_screen: float,
    rows: int,
    epochs: int,
    safety: float = 2.0,
    floor_s: float = 60,
) -> float:
    return max(float(floor_s), float(seconds_per_row_screen) * int(rows) * int(epochs) * float(safety))


def classify(
    returncode: int,
    stderr_tail: str,
    progress: list[dict],
    result_path: Path | None,
    killed_as: str | None = None,
) -> str | None:
    # Deterministic-first: NaN / blow-up before infra symptoms.
    if progress_diverged(progress):
        return "diverged"
    if killed_as == "stall":
        return "stall"
    if killed_as == "timeout":
        return "timeout"
    if "CUDA out of memory" in (stderr_tail or ""):
        return "cuda_oom"
    stderr_empty = not (stderr_tail or "").strip()
    if returncode in (-9, 137) and stderr_empty:
        return "host_oom"
    if returncode == 0 and not _result_valid(result_path):
        return "contract_violation"
    if returncode != 0:
        return "crash"
    return None


class LocalBackend:
    """Popen + progress.jsonl poll; stall watchdog and hard timeout."""

    def __init__(
        self,
        poll_s: float = 1.0,
        stall_threshold_s: float | None = None,
    ) -> None:
        self.poll_s = poll_s
        self.stall_threshold_s = stall_threshold_s

    def run(
        self,
        workspace: Path,
        cmd: list[str],
        env: dict,
        timeout_s: float,
        on_progress: Callable[[dict], None],
    ) -> Completed:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        progress_path = workspace / "progress.jsonl"
        if progress_path.exists():
            progress_path.unlink()

        t0 = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        offset = 0
        progress_seen: list[dict] = []
        progress_wall: list[float] = []
        first_loss: float | None = None
        last_progress_at = t0
        killed_as: str | None = None
        stderr_chunks: list[str] = []

        def _read_stderr() -> None:
            assert proc.stderr is not None
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        try:
            while True:
                if progress_path.is_file():
                    data = progress_path.read_bytes()
                    if len(data) > offset:
                        chunk = data[offset:]
                        offset = len(data)
                        for line in chunk.decode("utf-8", errors="replace").splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                row = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            now = time.monotonic()
                            progress_seen.append(row)
                            progress_wall.append(now)
                            last_progress_at = now
                            on_progress(row)
                            loss = row.get("loss")
                            if loss is not None:
                                lv = float(loss)
                                if first_loss is None:
                                    first_loss = lv if not (math.isnan(lv) or math.isinf(lv)) else None
                                if _is_bad_loss(lv, first_loss if first_loss is not None else lv):
                                    killed_as = "diverged"
                                    proc.kill()
                                    break

                if killed_as:
                    break

                rc = proc.poll()
                now = time.monotonic()
                if rc is not None:
                    break

                if now - t0 >= timeout_s:
                    killed_as = "timeout"
                    proc.kill()
                    break

                # Stall watchdog: last progress older than threshold.
                threshold = self.stall_threshold_s
                if threshold is None:
                    if len(progress_wall) >= 2:
                        gaps = [
                            progress_wall[i] - progress_wall[i - 1]
                            for i in range(1, len(progress_wall))
                        ]
                        threshold = max(DEFAULT_STALL_S, 3.0 * statistics.median(gaps))
                    else:
                        threshold = DEFAULT_STALL_S
                # Only arm stall after at least one progress line (else hang-before-start → timeout).
                if progress_seen and (now - last_progress_at) >= threshold:
                    killed_as = "stall"
                    proc.kill()
                    break

                time.sleep(self.poll_s)

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        finally:
            stderr_thread.join(timeout=2)

        wall_s = time.monotonic() - t0
        stderr_tail = "".join(stderr_chunks)[-4000:]
        returncode = proc.returncode if proc.returncode is not None else -9
        # Diverged kill is classified from progress; don't label as timeout/stall.
        if killed_as == "diverged":
            killed_as = None
        return Completed(
            returncode=returncode,
            stderr_tail=stderr_tail,
            wall_s=wall_s,
            killed_as=killed_as,
        )


class Runner:
    def __init__(
        self,
        events: EventLog,
        task: Task,
        run_cfg: dict,
        backend: Backend | None = None,
        heartbeat_s: float = 30.0,
    ) -> None:
        self.events = events
        self.task = task
        self.run_cfg = dict(run_cfg)
        stall = self.run_cfg.get("stall_threshold_s")
        poll = float(self.run_cfg.get("poll_s", 1.0))
        if backend is None:
            backend = LocalBackend(
                poll_s=poll,
                stall_threshold_s=float(stall) if stall is not None else None,
            )
        self.backend = backend
        self.heartbeat_s = float(heartbeat_s)

    def run(
        self,
        node: Node,
        rung: Rung,
        seed: int,
        timeout_s: float,
        env_overrides: dict | None = None,
        attempt: int = 1,
    ) -> RunResult:
        overrides = dict(env_overrides or {})
        paths: TaskPaths = self.run_cfg["paths"]
        run_dir = Path(self.run_cfg["run_dir"])
        workspace = (
            run_dir / "attempts" / f"node-{node.id}" / f"attempt-{attempt}"
        )
        workspace.mkdir(parents=True, exist_ok=True)

        spec = RUNG_ENV[rung]
        env = self._build_env(
            workspace=workspace,
            paths=paths,
            seed=seed,
            rung=rung,
            overrides=overrides,
            epochs=spec.epochs,
            max_rows=spec.max_rows,
        )

        progress: list[dict] = []
        last_prog: dict = {"step": 0, "total": 0, "loss": None}
        stop_hb = threading.Event()

        def on_progress(row: dict) -> None:
            progress.append(row)
            last_prog.update(row)

        def hb_loop() -> None:
            worker = f"node-{node.id}"
            while not stop_hb.wait(self.heartbeat_s):
                self.events.heartbeat(
                    worker,
                    node=node.id,
                    step=last_prog.get("step"),
                    total=last_prog.get("total"),
                    loss=last_prog.get("loss"),
                    attempt=attempt,
                )

        self._stage_candidate(workspace)

        hb_thread = threading.Thread(target=hb_loop, name="runner-heartbeat", daemon=True)
        hb_thread.start()
        try:
            completed = self.backend.run(
                workspace=workspace,
                cmd=[sys.executable, "template.py"],
                env=env,
                timeout_s=timeout_s,
                on_progress=on_progress,
            )
        finally:
            stop_hb.set()
            hb_thread.join(timeout=2)

        result_path = workspace / "result.json"
        failure = classify(
            completed.returncode,
            completed.stderr_tail,
            progress,
            result_path if result_path.is_file() else None,
            killed_as=completed.killed_as,
        )

        if failure is None:
            preds = self._preds_from_result(result_path)
            if spec.score_split is None:
                metrics: dict[str, float] = {}
            else:
                metrics = self.task.score(preds, spec.score_split)
            return RunResult(
                node=node.id,
                attempt=attempt,
                seed=seed,
                rung=rung,
                ok=True,
                metrics=metrics,
                failure_class=None,
                stderr_tail=completed.stderr_tail[-500:],
                gpu_s=0.0,
                wall_s=completed.wall_s,
                result_path=result_path,
                checkpoint_path=self._latest_checkpoint(workspace),
            )

        event_returncode = completed.returncode
        if failure == "host_oom" and event_returncode in (-9, 137):
            event_returncode = 137

        summary = self._failure_summary(node.id, failure, attempt)
        self.events.emit(
            "failure",
            node=node.id,
            attempt=attempt,
            stderr_tail=completed.stderr_tail[-500:],
            returncode=event_returncode,
            summary=summary,
            **{"class": failure},
        )

        recover = RECOVERY.get(failure)
        if recover is not None and attempt < 2:
            new_env = recover(env)
            action = RECOVERY_ACTION.get(failure, "retry")
            self.events.emit(
                "recovery",
                node=node.id,
                attempt=attempt,
                action=action,
                summary=f"node {node.id} recovery: {action} after {failure}",
                **{"class": failure},
            )
            # Map recovered env back to overrides for attempt 2 (BATCH etc.).
            next_overrides = {
                **overrides,
                **{
                    k: new_env[k]
                    for k in ("BATCH", "LR", "EPOCHS", "FEATURES", "DEVICE")
                    if k in new_env
                },
            }
            # Preserve failure injection overrides.
            if "SYNTHETIC_FAIL" in overrides:
                next_overrides["SYNTHETIC_FAIL"] = overrides["SYNTHETIC_FAIL"]
            return self.run(
                node,
                rung,
                seed,
                timeout_s,
                env_overrides=next_overrides,
                attempt=attempt + 1,
            )

        return RunResult(
            node=node.id,
            attempt=attempt,
            seed=seed,
            rung=rung,
            ok=False,
            metrics={},
            failure_class=failure,
            stderr_tail=completed.stderr_tail[-500:],
            gpu_s=0.0,
            wall_s=completed.wall_s,
            result_path=result_path if result_path.is_file() else None,
            checkpoint_path=self._latest_checkpoint(workspace),
        )

    def _stage_candidate(self, workspace: Path) -> None:
        """Copy template + report into the attempt dir (never import harness.*).

        Phase 6 may set ``run_cfg["candidate_src"]`` to the git Workspace working
        tree so patches apply; otherwise copies from repo ``candidate/``.
        """
        src_dir = Path(self.run_cfg["candidate_src"]) if self.run_cfg.get("candidate_src") else CANDIDATE_DIR
        for name in ("template.py", "report.py"):
            src = src_dir / name
            if not src.is_file():
                raise FileNotFoundError(f"missing candidate script: {src}")
            shutil.copy2(src, workspace / name)

    def _failure_summary(self, node_id: int, failure: str, attempt: int) -> str:
        if failure == "diverged":
            return (
                f"node {node_id} failed: diverged (attempt {attempt}); "
                f"given_up:diverged — NaN/blow-up is deterministic; family note: abandon"
            )
        return f"node {node_id} failed: {failure} (attempt {attempt})"

    def _resolve_paths(self, paths: TaskPaths) -> TaskPaths:
        return TaskPaths(
            train=Path(paths.train).resolve(),
            search_validation=Path(paths.search_validation).resolve(),
            holdout_validation=Path(paths.holdout_validation).resolve(),
            scoring_script=(
                Path(paths.scoring_script).resolve()
                if paths.scoring_script is not None
                else None
            ),
        )

    def _build_env(
        self,
        workspace: Path,
        paths: TaskPaths,
        seed: int,
        rung: Rung,
        overrides: dict,
        epochs: int | None,
        max_rows: int | None,
    ) -> dict:
        # Start from a minimal capability-safe copy of the host env.
        env = {
            k: v
            for k, v in os.environ.items()
            if "holdout" not in k.lower()
            and "rulebook" not in k.lower()
            and "protocols/" not in k
            and "protocols/" not in v
            and "holdout" not in v.lower()
            and "rulebook" not in v.lower()
        }
        # Do not point PYTHONPATH at the harness package root.
        root = Path(__file__).resolve().parents[1]
        pp = env.get("PYTHONPATH", "")
        if pp:
            parts = [
                p
                for p in pp.split(os.pathsep)
                if p and Path(p).resolve() != root
            ]
            if parts:
                env["PYTHONPATH"] = os.pathsep.join(parts)
            else:
                env.pop("PYTHONPATH", None)

        base = {
            "DEVICE": str(self.run_cfg.get("device", "cpu")),
            "SEED": str(seed),
            "WORKSPACE": str(workspace.resolve()),
            "BATCH": str(self.run_cfg.get("batch", 1024)),
            "LR": str(self.run_cfg.get("lr", "1e-3")),
            "EPOCHS": str(
                epochs if epochs is not None else self.run_cfg.get("epochs", 1)
            ),
            "FEATURES": str(self.run_cfg.get("features", "base")),
        }
        resolved = self._resolve_paths(paths)
        if rung == "holdout":
            candidate_paths = {
                "TRAIN": str(resolved.train),
                "VALID": str(resolved.holdout_validation),
            }
        else:
            candidate_paths = self.task.candidate_env(resolved)
        base.update(candidate_paths)
        base.update({k: str(v) for k, v in overrides.items()})
        if max_rows is not None:
            base["MAX_ROWS"] = str(max_rows)
        env.update(base)

        device = env.get("DEVICE", "cpu")
        if device.startswith("cuda"):
            gpu = self.run_cfg.get("cuda_visible_devices")
            if gpu is not None:
                env["CUDA_VISIBLE_DEVICES"] = str(gpu)

        # Capability: never pass holdout or protocol paths.
        env.pop("HOLDOUT", None)
        if rung != "holdout":
            assert set(candidate_paths) <= {"TRAIN", "VALID"}
        return env

    @staticmethod
    def _preds_from_result(result_path: Path) -> Path:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return Path(data["preds"])

    @staticmethod
    def _latest_checkpoint(workspace: Path) -> Path | None:
        ckpt_dir = workspace / "checkpoints"
        if not ckpt_dir.is_dir():
            return None
        files = sorted(
            ckpt_dir.glob("step-*.pt"),
            key=lambda p: int(p.stem.split("-", 1)[1]),
        )
        return files[-1] if files else None
