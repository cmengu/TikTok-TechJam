"""Phase 3: candidate template + report contract (50K synthetic)."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import pyarrow.parquet as pq

from harness.tasks.synthetic import SyntheticTask
from helpers import placeholder_protocol, run_candidate, stage_candidate

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "candidate" / "synthetic" / "template.py"
REPORT = ROOT / "candidate" / "report.py"


@pytest.fixture(scope="module")
def synth_50k(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth50k")
    proto = placeholder_protocol(root)
    task = SyntheticTask(n_impressions=50_000)
    paths = task.prepare(proto, root / "data")
    return task, paths, root


def test_contract_outputs(synth_50k, tmp_path: Path):
    task, paths, _root = synth_50k
    ws = tmp_path / "ws"
    proc = run_candidate(paths, ws)
    assert proc.returncode == 0, proc.stderr
    progress = (ws / "progress.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(progress) >= 2
    result = json.loads((ws / "result.json").read_text(encoding="utf-8"))
    assert result["metrics"] == {}
    preds = pq.read_table(ws / "preds.parquet")
    valid = pq.read_table(paths.search_validation)
    assert preds.num_rows == valid.num_rows
    scored = task.score(Path(result["preds"]), "search")
    assert "ctr_auc" in scored and "cvr_auc" in scored
    ckpts = list((ws / "checkpoints").glob("step-*.pt"))
    assert ckpts
    assert len(ckpts) <= 3


def test_features_env_changes_model(synth_50k, tmp_path: Path):
    task, paths, _root = synth_50k
    ws_base = tmp_path / "base"
    ws_leak = tmp_path / "leak"
    a = run_candidate(paths, ws_base, seed=1, features="base")
    b = run_candidate(paths, ws_leak, seed=1, features="base,f_leak")
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, b.stderr
    m_a = task.score(Path(json.loads((ws_base / "result.json").read_text())["preds"]), "search")
    m_b = task.score(Path(json.loads((ws_leak / "result.json").read_text())["preds"]), "search")
    assert m_b["cvr_auc"] - m_a["cvr_auc"] > 0.2


def test_seed_changes_result(synth_50k, tmp_path: Path):
    task, paths, _root = synth_50k
    ws1 = tmp_path / "s1"
    ws2 = tmp_path / "s2"
    ws1b = tmp_path / "s1b"
    r1 = run_candidate(paths, ws1, seed=1)
    r2 = run_candidate(paths, ws2, seed=2)
    r1b = run_candidate(paths, ws1b, seed=1)
    assert r1.returncode == r2.returncode == r1b.returncode == 0
    m1 = task.score(Path(json.loads((ws1 / "result.json").read_text())["preds"]), "search")
    m2 = task.score(Path(json.loads((ws2 / "result.json").read_text())["preds"]), "search")
    m1b = task.score(Path(json.loads((ws1b / "result.json").read_text())["preds"]), "search")
    assert m1["cvr_auc"] != m2["cvr_auc"]
    assert m1["cvr_auc"] == m1b["cvr_auc"]


@pytest.mark.parametrize(
    "mode,check",
    [
        ("crash", "exit_1"),
        ("oom_cuda", "cuda_oom"),
        ("oom_host", "sigkill"),
        ("nan", "nan_progress"),
        ("hang", "still_running"),
        ("no_result", "no_result_json"),
        ("bad_schema", "missing_preds"),
    ],
)
def test_failure_modes_observable(synth_50k, tmp_path: Path, mode: str, check: str):
    _task, paths, _root = synth_50k
    ws = tmp_path / mode
    stage_candidate(ws)
    env = {
        **os.environ,
        "TRAIN": str(paths.train),
        "VALID": str(paths.search_validation),
        "DEVICE": "cpu",
        "SEED": "0",
        "FEATURES": "base",
        "BATCH": "1024",
        "EPOCHS": "1",
        "WORKSPACE": str(ws),
        "SYNTHETIC_FAIL": mode,
        "LR": "1e-3",
    }
    cmd = [sys.executable, "template.py"]
    if check == "still_running":
        proc = subprocess.Popen(
            cmd, cwd=str(ws), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            time.sleep(3)
            assert proc.poll() is None
        finally:
            proc.kill()
            proc.wait(timeout=5)
        return

    proc = subprocess.run(cmd, cwd=str(ws), env=env, capture_output=True, text=True)
    if check == "exit_1":
        assert proc.returncode == 1
        assert "SYNTHETIC_FAIL=crash" in proc.stderr or "Traceback" in proc.stderr
    elif check == "cuda_oom":
        assert proc.returncode != 0
        assert "CUDA out of memory" in proc.stderr
    elif check == "sigkill":
        assert proc.returncode in (-9, 137)
    elif check == "nan_progress":
        assert proc.returncode == 0
        lines = (ws / "progress.jsonl").read_text().splitlines()
        assert any("NaN" in ln or "nan" in ln for ln in lines)
    elif check == "no_result_json":
        assert proc.returncode == 0
        assert not (ws / "result.json").exists()
    elif check == "missing_preds":
        assert proc.returncode == 0
        result = json.loads((ws / "result.json").read_text())
        assert not Path(result["preds"]).exists()


def test_report_imports_stdlib_only():
    tree = ast.parse(REPORT.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name.startswith("harness") for name in imports)
    top_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_imports.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_imports.append((node.module or "").split(".")[0])
    allowed = {"json", "os", "time", "pathlib", "annotations", "__future__", ""}
    for name in top_imports:
        assert name in allowed


def test_template_does_not_import_harness():
    tree = ast.parse(TEMPLATE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("harness") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("harness")


def test_runs_under_60s_cpu(synth_50k, tmp_path: Path):
    _task, paths, _root = synth_50k
    ws = tmp_path / "ws"
    t0 = time.perf_counter()
    proc = run_candidate(paths, ws)
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 60.0
