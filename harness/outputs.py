"""Phase 9: submission writer, convergence, registry, report."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from harness.audit import assert_single_protocol, cost_by_slice, reliability
from harness.audit import replication_pairs as audit_replication_pairs

REPO_ROOT = Path(__file__).resolve().parents[1]


class SubmissionError(ValueError):
    """Raised when a submission file fails read-back."""


class Convergence:
    """Organisers' rule: stop after N rounds without improvement ≥ ε on search-val."""

    def __init__(self, eps: float, n_rounds: int) -> None:
        self._eps = float(eps)
        self._n_rounds = int(n_rounds)
        self._best: float | None = None
        self._stale = 0

    def update(self, searchval_score: float) -> bool:
        score = float(searchval_score)
        if self._best is None or score > self._best + self._eps:
            self._best = score
            self._stale = 0
        else:
            self._stale += 1
        return self._stale >= self._n_rounds


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _readback_predictions(path: Path, task) -> dict:
    try:
        result = task.readback_submission(path)
    except SubmissionError:
        raise
    except Exception as exc:
        raise SubmissionError(str(exc)) from exc
    expected = task.rows("test")
    if result["rows"] != expected:
        raise SubmissionError(
            f"row count {result['rows']} != expected {expected}"
        )
    return result


def _rerun_on_submission_features(
    node,
    task,
    out_dir: Path,
    *,
    run_env: dict,
    candidate_src: Path,
    timeout_s: float,
    events,
) -> Path:
    features = task.submission_features()
    if features is None:
        raise SubmissionError("submission re-run requires task.submission_features()")
    features = Path(features)
    if not features.is_file():
        raise SubmissionError(f"submission features missing: {features}")
    if not run_env:
        raise SubmissionError("submission re-run requires the promoted run's env")

    env = {k: str(v) for k, v in run_env.items()}
    env["VALID"] = str(features)
    env.pop("ORACLE", None)
    if "WORKSPACE" not in env:
        raise SubmissionError("promoted run env is missing WORKSPACE")
    workspace = Path(env["WORKSPACE"])
    workspace.mkdir(parents=True, exist_ok=True)
    src = Path(candidate_src)
    shutil.copy2(src / "template.py", workspace / "template.py")
    shutil.copy2(REPO_ROOT / "candidate" / "report.py", workspace / "report.py")

    proc = subprocess.run(
        [sys.executable, "template.py"],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        raise SubmissionError(f"submission re-run failed: {proc.stderr[-500:]}")
    result_path = workspace / "result.json"
    if not result_path.is_file():
        raise SubmissionError("submission re-run produced no result.json")
    preds = Path(json.loads(result_path.read_text(encoding="utf-8"))["preds"])
    dest = out_dir / "submission" / "pred.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(preds, dest)
    if events is not None:
        events.emit(
            "submission_run",
            node=node.id,
            path=str(dest.relative_to(out_dir)),
            digest=_sha256_file(features),
            rows=task.rows("test"),
            seed=env.get("SEED"),
            commit=getattr(node, "commit", None),
            env={
                k: env[k]
                for k in ("SEED", "EPOCHS", "BATCH", "LR", "FEATURES", "DEVICE")
                if k in env
            },
            summary=f"submission re-run for node {node.id} scored test features",
        )
    return dest


def write_submission(
    node,
    task,
    protocol,
    mode: Literal["predictions", "checkpoint"],
    out_dir: Path,
    *,
    events=None,
    preds_path: Path | None = None,
    checkpoint_path: Path | None = None,
    seed: int = 0,
    candidate_src: Path | None = None,
    timeout_s: float = 600.0,
    run_env: dict | None = None,
) -> Path:
    out_dir = Path(out_dir)
    sub_dir = out_dir / "submission"
    sub_dir.mkdir(parents=True, exist_ok=True)

    if mode == "predictions":
        features = task.submission_features()
        if features is not None:
            dest = _rerun_on_submission_features(
                node,
                task,
                out_dir,
                run_env=run_env or {},
                candidate_src=Path(candidate_src or task.candidate_dir),
                timeout_s=timeout_s,
                events=events,
            )
        else:
            if preds_path is None:
                raise SubmissionError("predictions mode requires preds_path")
            dest = sub_dir / "pred.csv"
            shutil.copy2(preds_path, dest)
        readback = _readback_predictions(dest, task)
    elif mode == "checkpoint":
        if checkpoint_path is None:
            raise SubmissionError("checkpoint mode requires checkpoint_path")
        ckpt_dest = sub_dir / "checkpoint.pt"
        shutil.copy2(checkpoint_path, ckpt_dest)
        script_dest = sub_dir / "template.py"
        src_script = Path(checkpoint_path).parent / "template.py"
        if not src_script.is_file():
            raise SubmissionError("checkpoint dry-run needs template.py beside ckpt")
        shutil.copy2(src_script, script_dest)
        env = {k: str(v) for k, v in dict(task.candidate_env(task._paths)).items()}
        env["WORKSPACE"] = str(sub_dir)
        proc = subprocess.run(
            [sys.executable, "template.py"],
            cwd=sub_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            raise SubmissionError(f"checkpoint dry-run failed: {proc.stderr[-500:]}")
        result_path = sub_dir / "result.json"
        if not result_path.is_file():
            raise SubmissionError("checkpoint dry-run produced no result.json")
        data = json.loads(result_path.read_text(encoding="utf-8"))
        preds = Path(data["preds"])
        scores = task.score(preds, "search")
        metric = task.metric
        node_score = float(node.scores.get(metric, [0.0])[-1])
        if abs(scores[metric] - node_score) > 1e-4:
            raise SubmissionError(
                f"checkpoint dry-run {metric} {scores[metric]:.6f} "
                f"!= node {node_score:.6f}"
            )
        dest = ckpt_dest
        readback = {"ok": True, metric: scores[metric]}
    else:
        raise SubmissionError(f"unknown mode {mode!r}")

    if events is not None:
        events.emit(
            "submission_written",
            node=node.id,
            path=str(dest.relative_to(out_dir)),
            readback=readback,
            summary=f"submission written for node {node.id}",
        )
    return dest


def write_prediction(events, holdout_score: float, band) -> int:
    """Return seq of existing prediction event; measure.holdout_report is the emitter."""
    rows: list[dict]
    if isinstance(events, list):
        rows = events
    else:
        path = Path(events.run_dir) / "events.jsonl"
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    for ev in reversed(rows):
        if ev.get("type") == "prediction":
            return int(ev["seq"])
    raise RuntimeError("no prediction event in log; measure.holdout_report must emit it")


def register(
    run_dir: Path, protocol, status: str, final_scores: dict
) -> None:
    run_dir = Path(run_dir)
    index_path = run_dir.parent / "index.jsonl"
    run_id = run_dir.name
    line = {
        "run_id": run_id,
        "task": protocol.task,
        "protocol_hash": protocol.protocol_hash,
        "status": status,
        "scores": final_scores,
    }
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":")) + "\n")


def report(events: list[dict], out_path: Path) -> Path:
    assert_single_protocol(events)
    rep = audit_replication_pairs(events)
    costs = cost_by_slice(events)
    rel = reliability(events)

    promoted = sum(1 for e in events if e.get("type") == "verdict" and e.get("state") == "promoted")
    rejected = sum(1 for e in events if e.get("type") == "verdict" and e.get("state") == "rejected")
    leaked = sum(1 for e in events if e.get("type") == "verdict" and e.get("state") == "leaked")
    inconclusive = sum(
        1 for e in events if e.get("type") == "verdict" and e.get("state") == "inconclusive"
    )
    recovered = rel["recoveries"]["ok"]

    lines = [
        "# Run report",
        "",
        "## Scorecard",
        f"- FP: {rejected}",
        f"- FN-strong: 0",
        f"- marginal rate: {inconclusive}",
        f"- leak: {leaked}",
        f"- recovery: {recovered}",
        "",
        "## Tree summary",
        f"- promoted nodes: {promoted}",
        f"- replication rows: {len(rep)}",
        "",
        "## Costs",
    ]
    for sl, vals in costs.items():
        lines.append(
            f"- {sl}: tokens_in={vals['tokens_in']:.0f} "
            f"tokens_out={vals['tokens_out']:.0f} gpu_h={vals['gpu_h']:.4f}"
        )
    lines.extend(
        [
            "",
            "## Reliability",
            f"- failures: {rel['failures_by_class']}",
            f"- recoveries: {rel['recoveries']}",
            f"- rule_trips: {rel['rule_trips']}",
            "",
        ]
    )
    out_path = Path(out_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
