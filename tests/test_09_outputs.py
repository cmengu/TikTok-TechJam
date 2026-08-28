"""Phase 9: submission writer, convergence, registry, report."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from harness.events import EventLog
from harness.outputs import Convergence, SubmissionError, register, report, write_prediction
from harness.outputs import write_submission
from helpers import placeholder_protocol
from harness.tasks.synthetic import SyntheticTask
from harness.types import Cost, Node

ROOT = Path(__file__).resolve().parents[1]


def _node(node_id: int = 3) -> Node:
    return Node(
        id=node_id,
        parent=1,
        hypothesis_id="h-train-1",
        commit="abc",
        state="promoted",
        rung="replicate",
        kind="draft",
        scores={"cvr_auc": [0.529]},
        seeds=[1, 2, 3],
        cost=Cost(0.0, 0, 0, "training"),
        created_seq=1,
    )


def _write_preds(path: Path, n: int, bad_val: float | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sample_id", "p_click", "p_conversion_given_click"],
        )
        writer.writeheader()
        for i in range(n):
            writer.writerow(
                {
                    "sample_id": i,
                    "p_click": 0.1,
                    "p_conversion_given_click": bad_val if bad_val is not None else 0.2,
                }
            )


@pytest.fixture
def synth_task(tmp_path: Path):
    proto = placeholder_protocol(tmp_path)
    task = SyntheticTask(n_impressions=50_000)
    task.prepare(proto, tmp_path / "data", seed=0)
    return task, proto


def test_wrong_head_refused(synth_task, tmp_path: Path):
    task, proto = synth_task
    preds = tmp_path / "bad.csv"
    with preds.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sample_id", "p_click", "p_click_and_conversion"],
        )
        writer.writeheader()
        writer.writerow({"sample_id": 0, "p_click": 0.1, "p_click_and_conversion": 0.2})
    with pytest.raises(SubmissionError, match="p_conversion_given_click"):
        write_submission(_node(), task, proto, "predictions", tmp_path, preds_path=preds)


def test_readback_catches_row_count_and_range(synth_task, tmp_path: Path):
    task, proto = synth_task
    short = tmp_path / "short.csv"
    _write_preds(short, task.rows("test") - 1)
    with pytest.raises(SubmissionError, match="row count"):
        write_submission(_node(), task, proto, "predictions", tmp_path, preds_path=short)
    bad = tmp_path / "bad.csv"
    _write_preds(bad, task.rows("test"), bad_val=1.2)
    with pytest.raises(SubmissionError, match="out of"):
        write_submission(_node(), task, proto, "predictions", tmp_path, preds_path=bad)


def test_checkpoint_dry_run(synth_task, tmp_path: Path):
    task, proto = synth_task
    ws = tmp_path / "ws"
    ws.mkdir()
    ckpt = ws / "checkpoint.pt"
    ckpt.write_bytes(b"stub")
    (ws / "template.py").write_text(
        "import json\nfrom pathlib import Path\n"
        "Path('result.json').write_text(json.dumps({'preds': 'preds.parquet'}))\n",
        encoding="utf-8",
    )
    with pytest.raises((SubmissionError, FileNotFoundError)):
        write_submission(
            _node(), task, proto, "checkpoint", tmp_path, checkpoint_path=ckpt
        )


def test_convergence_rule():
    conv = Convergence(0.001, 3)
    seq = [0.50, 0.501, 0.501, 0.501, 0.502]
    hits = [conv.update(s) for s in seq]
    assert hits == [False, False, False, True, False]
    assert hits.index(True) == 3


def test_prediction_precedes_submission(tmp_path: Path):
    from harness.fake_run import write

    run_dir = tmp_path / "fake-0001"
    write(run_dir, instant=True)
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pred_seq = write_prediction(events, 0.527, None)
    sub_seq = next(e["seq"] for e in events if e["type"] == "submission_written")
    assert pred_seq < sub_seq


def test_registry_line(synth_task, tmp_path: Path):
    task, proto = synth_task
    run_dir = tmp_path / "run-abc"
    run_dir.mkdir()
    register(run_dir, proto, "completed", {"cvr_auc": 0.53})
    line = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").strip())
    assert line == {
        "run_id": "run-abc",
        "task": "synthetic",
        "protocol_hash": proto.protocol_hash,
        "status": "completed",
        "scores": {"cvr_auc": 0.53},
    }


def test_report_renders(tmp_path: Path):
    from harness.fake_run import write

    run_dir = tmp_path / "fake-0001"
    write(run_dir, instant=True)
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out = tmp_path / "report.md"
    report(events, out)
    text = out.read_text(encoding="utf-8")
    for heading in ("FP", "FN-strong", "marginal rate", "leak", "recovery"):
        assert heading in text
