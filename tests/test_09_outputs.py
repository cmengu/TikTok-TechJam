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


def _node(node_id: int = 3, commit: str = "abc") -> Node:
    return Node(
        id=node_id,
        parent=1,
        hypothesis_id="h-train-1",
        commit=commit,
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


def test_task_blind_layer_has_no_task_name():
    outputs = (ROOT / "harness" / "outputs.py").read_text(encoding="utf-8")
    tree = (ROOT / "harness" / "tree.py").read_text(encoding="utf-8")
    assert '"kuairand"' not in outputs
    assert "'kuairand'" not in outputs
    assert '"kuairand"' not in tree
    assert "'kuairand'" not in tree
    assert "cvr_auc" not in outputs


@pytest.mark.skipif(
    not (ROOT / "data" / "kuairand" / "train.csv").exists(),
    reason="KuaiRand splits not built",
)
def test_kuairand_submission_reruns_on_test_features(tmp_path: Path):
    from harness.protocol import load as load_protocol
    from harness.tasks.kuairand import KuaiRandTask

    proto = load_protocol(ROOT / "protocols" / "kuairand.yaml")
    task = KuaiRandTask()
    task.prepare(proto, tmp_path / "data")
    features = task.submission_features()
    assert features is not None
    n_test = task.rows("test")
    assert n_test == 170588

    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "template.py").write_text(
        "import csv, os\n"
        "from pathlib import Path\n"
        "import report\n"
        "valid = Path(os.environ['VALID'])\n"
        "ws = Path(os.environ['WORKSPACE'])\n"
        "rows = list(csv.DictReader(valid.open()))\n"
        "out = ws / 'preds.csv'\n"
        "with out.open('w', newline='') as fh:\n"
        "    w = csv.writer(fh)\n"
        "    w.writerow(['row_id', 'user_id', 'video_id', 'score'])\n"
        "    for i, row in enumerate(rows):\n"
        "        w.writerow([i, row['user_id'], row['video_id'], '0.5'])\n"
        "report.result({'primary': 0.0}, out)\n",
        encoding="utf-8",
    )

    events = EventLog(tmp_path / "run", "sub-test", proto)
    run_env = {
        "TRAIN": str(task._paths.train),
        "VALID": str(task._paths.search_validation),
        "WORKSPACE": str(tmp_path / "run" / "rerun"),
        "SEED": "0",
        "EPOCHS": "12",
        "BATCH": "2048",
        "LR": "0.001",
        "DEVICE": "cpu",
        "FEATURES": "base",
    }
    dest = write_submission(
        _node(),
        task,
        proto,
        "predictions",
        tmp_path / "run",
        events=events,
        seed=0,
        candidate_src=stub,
        timeout_s=60.0,
        run_env=run_env,
    )
    events.close()
    assert dest.is_file()
    readback = task.readback_submission(dest)
    assert readback["rows"] == n_test

    log = [
        json.loads(line)
        for line in (tmp_path / "run" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    run_ev = next(e for e in log if e["type"] == "submission_run")
    written = next(e for e in log if e["type"] == "submission_written")
    assert run_ev["node"] == 3
    assert run_ev["rows"] == n_test
    assert run_ev["digest"]
    assert run_ev["seed"] == "0"
    assert run_ev["env"]["EPOCHS"] == "12"
    assert run_ev["env"]["BATCH"] == "2048"
    assert written["seq"] > run_ev["seq"]


@pytest.mark.skipif(
    not (ROOT / "data" / "kuairand" / "train.csv").exists(),
    reason="KuaiRand splits not built",
)
def test_submission_rerun_uses_promoted_env_not_shell(tmp_path: Path, monkeypatch):
    from harness.protocol import load as load_protocol
    from harness.tasks.kuairand import KuaiRandTask

    monkeypatch.setenv("EPOCHS", "1")
    proto = load_protocol(ROOT / "protocols" / "kuairand.yaml")
    task = KuaiRandTask()
    task.prepare(proto, tmp_path / "data")
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "template.py").write_text(
        "import csv, json, os\n"
        "from pathlib import Path\n"
        "import report\n"
        "ws = Path(os.environ['WORKSPACE'])\n"
        "(ws / 'captured.json').write_text(json.dumps({"
        "'EPOCHS': os.environ.get('EPOCHS'), 'BATCH': os.environ.get('BATCH')"
        "}))\n"
        "valid = Path(os.environ['VALID'])\n"
        "rows = list(csv.DictReader(valid.open()))\n"
        "out = ws / 'preds.csv'\n"
        "with out.open('w', newline='') as fh:\n"
        "    w = csv.writer(fh)\n"
        "    w.writerow(['row_id', 'user_id', 'video_id', 'score'])\n"
        "    for i, row in enumerate(rows):\n"
        "        w.writerow([i, row['user_id'], row['video_id'], '0.5'])\n"
        "report.result({}, out)\n",
        encoding="utf-8",
    )
    events = EventLog(tmp_path / "run", "env-test", proto)
    ws = tmp_path / "run" / "rerun"
    dest = write_submission(
        _node(commit="abc123"),
        task,
        proto,
        "predictions",
        tmp_path / "run",
        events=events,
        candidate_src=stub,
        timeout_s=60.0,
        run_env={
            "TRAIN": str(task._paths.train),
            "VALID": str(task._paths.search_validation),
            "WORKSPACE": str(ws),
            "SEED": "7",
            "EPOCHS": "12",
            "BATCH": "2048",
            "LR": "0.001",
            "DEVICE": "cpu",
            "FEATURES": "base",
        },
    )
    events.close()
    captured = json.loads((ws / "captured.json").read_text())
    assert captured["EPOCHS"] == "12"
    assert captured["BATCH"] == "2048"
    log = [
        json.loads(line)
        for line in (tmp_path / "run" / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    run_ev = next(e for e in log if e["type"] == "submission_run")
    assert run_ev["env"]["EPOCHS"] == "12"
    assert run_ev["env"]["BATCH"] == "2048"
    assert run_ev["env"]["SEED"] == "7"
    assert run_ev["commit"] == "abc123"
    assert dest.is_file()
