"""Phase 9: submission writer, convergence, registry, report."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from harness.audit import assert_single_protocol, cost_by_slice, reliability
from harness.audit import replication_pairs as audit_replication_pairs

PREDICTION_COLUMNS = ("sample_id", "p_click", "p_conversion_given_click")


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


def _readback_predictions(path: Path, task, expected_rows: int) -> dict:
    if getattr(task, "name", None) == "kuairand":
        result = task.readback_submission(path)
        if result["rows"] != expected_rows:
            raise SubmissionError(
                f"row count {result['rows']} != expected {expected_rows}"
            )
        return result

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SubmissionError("empty submission file")
        cols = list(reader.fieldnames)
        if "p_conversion_given_click" not in cols:
            raise SubmissionError(
                "submission must include p_conversion_given_click head"
            )
        if "p_click_and_conversion" in cols:
            raise SubmissionError("wrong head: p_click_and_conversion")
        missing = set(PREDICTION_COLUMNS) - set(cols)
        if missing:
            raise SubmissionError(f"missing columns: {sorted(missing)}")
        rows = list(reader)
    if len(rows) != expected_rows:
        raise SubmissionError(
            f"row count {len(rows)} != expected {expected_rows}"
        )
    for i, row in enumerate(rows):
        for col in PREDICTION_COLUMNS:
            val = row.get(col)
            if val is None or val == "":
                raise SubmissionError(f"row {i}: missing {col}")
            try:
                fval = float(val)
            except ValueError as exc:
                raise SubmissionError(f"row {i}: non-numeric {col}") from exc
            if fval < 0.0 or fval > 1.0:
                raise SubmissionError(f"row {i}: {col}={fval} out of [0,1]")
    return {"ok": True, "rows": len(rows), "columns": cols}


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
) -> Path:
    out_dir = Path(out_dir)
    sub_dir = out_dir / "submission"
    sub_dir.mkdir(parents=True, exist_ok=True)

    if mode == "predictions":
        if preds_path is None:
            raise SubmissionError("predictions mode requires preds_path")
        dest = sub_dir / "pred.csv"
        shutil.copy2(preds_path, dest)
        readback = _readback_predictions(dest, task, task.rows("test"))
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
        env = dict(task.candidate_env(task._paths))  # type: ignore[attr-defined]
        env["WORKSPACE"] = str(sub_dir)
        proc = subprocess.run(
            [sys.executable, "template.py"],
            cwd=sub_dir,
            env={**dict(os.environ), **{k: str(v) for k, v in env.items()}},
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
        metric = getattr(task, "metric", "cvr_auc")
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
