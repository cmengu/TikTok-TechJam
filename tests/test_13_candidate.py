"""Step 6: KuaiRand FM candidate template tests."""

from __future__ import annotations

import ast
import csv
import json
import re
from pathlib import Path

import pytest

from harness.kit import KIT_DIR, kit_module
from harness.protocol import load as load_protocol
from harness.tasks.kuairand import KuaiRandTask
from helpers import run_candidate

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocols" / "kuairand.yaml"
TEMPLATE = ROOT / "candidate" / "kuairand" / "template.py"

pytestmark = pytest.mark.skipif(
    not (ROOT / "data" / "kuairand" / "train.csv").exists(),
    reason="KuaiRand splits not built",
)


@pytest.fixture(scope="module")
def kuairand_paths(tmp_path_factory):
    proto = load_protocol(PROTOCOL_PATH)
    task = KuaiRandTask()
    root = tmp_path_factory.mktemp("kr-cand")
    paths = task.prepare(proto, root / "data")
    return task, paths, root


def _fast_run(paths, ws: Path, *, seed: int = 0, epochs: int = 2):
    return run_candidate(
        paths,
        ws,
        seed=seed,
        epochs=epochs,
        batch=8192,
        timeout=120.0,
        candidate_dir=ROOT / "candidate" / "kuairand",
        max_rows=50_000,
    )


@pytest.mark.slow
def test_baseline_reproduces_fm_score(kuairand_paths, tmp_path: Path):
    task, paths, _root = kuairand_paths
    ws = tmp_path / "ws"
    proc = run_candidate(
        paths,
        ws,
        seed=0,
        epochs=11,
        batch=8192,
        timeout=300.0,
        candidate_dir=task.candidate_dir,
    )
    assert proc.returncode == 0, proc.stderr
    preds = ws / "preds.csv"
    assert preds.is_file()
    metrics = task.score(preds, "search")
    assert abs(metrics["primary"] - 0.6016) < 0.003


def test_rules_jsonl_valid():
    lines = (ROOT / "candidate" / "rules.jsonl").read_text().strip().splitlines()
    assert len(lines) == 9
    for line in lines:
        json.loads(line)


def test_every_require_rule_matches_the_template():
    src = TEMPLATE.read_text(encoding="utf-8")
    for line in (ROOT / "candidate" / "rules.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        rule = json.loads(line)
        if rule["mode"] != "require" or not rule.get("pattern"):
            continue
        assert re.search(rule["pattern"], src), f"{rule['id']} {rule['pattern']}"


def test_template_emits_required_columns(kuairand_paths, tmp_path: Path):
    task, paths, _root = kuairand_paths
    ws = tmp_path / "ws"
    proc = _fast_run(paths, ws, epochs=1)
    assert proc.returncode == 0, proc.stderr
    preds = ws / "preds.csv"
    with preds.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == ["row_id", "user_id", "video_id", "score"]
    submit = kit_module("submit")
    raw = ROOT / "data" / "raw"
    data_dir = raw if raw.exists() else KIT_DIR / "KuaiRand-Pure" / "data"
    rows = kit_module("data").load(str(data_dir.resolve()))["valid"]
    submit.read_submission(str(preds), rows)


def test_candidate_imports_no_torch():
    forbidden = {"torch", "pyarrow"}
    paths = [*(ROOT / "candidate" / "kuairand").rglob("*.py"), ROOT / "candidate" / "report.py"]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
                assert names.isdisjoint(forbidden), path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".", 1)[0] not in forbidden, path


def test_template_honours_seed(kuairand_paths, tmp_path: Path):
    _task, paths, _root = kuairand_paths
    a = tmp_path / "a"
    b = tmp_path / "b"
    c = tmp_path / "c"
    assert _fast_run(paths, a, seed=1).returncode == 0
    assert _fast_run(paths, b, seed=1).returncode == 0
    assert _fast_run(paths, c, seed=2).returncode == 0
    pa = (a / "preds.csv").read_bytes()
    pb = (b / "preds.csv").read_bytes()
    pc = (c / "preds.csv").read_bytes()
    assert pa == pb
    assert pa != pc


def test_progress_and_checkpoint_per_epoch(kuairand_paths, tmp_path: Path):
    _task, paths, _root = kuairand_paths
    ws = tmp_path / "ws"
    epochs = 2
    assert _fast_run(paths, ws, epochs=epochs).returncode == 0
    progress = [
        json.loads(line)
        for line in (ws / "progress.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert [row["step"] for row in progress] == list(range(1, epochs + 1))
    ckpts = sorted((ws / "checkpoints").glob("step-*.pt"))
    assert [int(p.stem.split("-", 1)[1]) for p in ckpts] == list(range(1, epochs + 1))
    for path in ckpts:
        raw = path.read_bytes()
        assert len(raw) > 64
        assert raw != f"epoch-{path.stem.split('-', 1)[1]}".encode()


def test_labelled_valid_does_not_change_preds(kuairand_paths, tmp_path: Path):
    task, paths, _root = kuairand_paths
    labelled = tmp_path / "valid_labelled.csv"
    labels = task._labels["search"]
    with paths.search_validation.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if "long_view" not in fieldnames:
        fieldnames = [*fieldnames, "long_view"]
    with labelled.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row, lab in zip(rows, labels, strict=True):
            out = dict(row)
            out["long_view"] = lab["long_view"]
            writer.writerow(out)

    class _Paths:
        train = paths.train
        search_validation = labelled

    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    assert _fast_run(paths, clean, seed=0).returncode == 0
    assert _fast_run(_Paths(), dirty, seed=0).returncode == 0
    assert (clean / "preds.csv").read_bytes() == (dirty / "preds.csv").read_bytes()


def test_fast_contract_two_epochs(kuairand_paths, tmp_path: Path):
    task, paths, _root = kuairand_paths
    ws = tmp_path / "ws"
    proc = _fast_run(paths, ws, epochs=2)
    assert proc.returncode == 0, proc.stderr
    metrics = task.score(ws / "preds.csv", "search")
    assert "primary" in metrics
    assert 0.0 < metrics["primary"] < 1.0
