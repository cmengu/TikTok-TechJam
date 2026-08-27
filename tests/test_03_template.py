"""Phase 3: candidate template + report contract (50K synthetic)."""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from harness.protocol import load
from harness.tasks.synthetic import SyntheticTask

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocols" / "synthetic.yaml"
TEMPLATE = ROOT / "harness" / "candidate" / "template.py"
REPORT = ROOT / "harness" / "candidate" / "report.py"


def _placeholder_protocol(tmp_path: Path):
    raw = copy.deepcopy(yaml.safe_load(PROTOCOL.read_text()))
    raw["ruler"]["data"]["train"]["sha256"] = "0" * 63 + "1"
    raw["ruler"]["data"]["test"]["sha256"] = "0" * 63 + "2"
    raw["ruler"]["splits"]["search_validation"]["sha256"] = "0" * 63 + "3"
    raw["ruler"]["splits"]["holdout_validation"]["sha256"] = "0" * 63 + "4"
    raw["ruler"]["scoring"]["script_sha"] = "0" * 63 + "5"
    path = tmp_path / "proto.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load(path)


@pytest.fixture(scope="module")
def synth_50k(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth50k")
    proto = _placeholder_protocol(root)
    task = SyntheticTask(n_impressions=50_000)
    paths = task.prepare(proto, root / "data")
    return task, paths, root


def _run_template(paths, ws: Path, *, seed=0, features="base", fail="", epochs=1, batch=1024):
    ws.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "TRAIN": str(paths.train),
        "VALID": str(paths.search_validation),
        "DEVICE": "cpu",
        "SEED": str(seed),
        "FEATURES": features,
        "BATCH": str(batch),
        "EPOCHS": str(epochs),
        "WORKSPACE": str(ws),
        "LR": "1e-3",
    }
    if fail:
        env["SYNTHETIC_FAIL"] = fail
    else:
        env.pop("SYNTHETIC_FAIL", None)
    return subprocess.run(
        [sys.executable, "-m", "harness.candidate.template"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def test_contract_outputs(synth_50k, tmp_path: Path):
    _task, paths, _root = synth_50k
    ws = tmp_path / "ws"
    proc = _run_template(paths, ws)
    assert proc.returncode == 0, proc.stderr
    progress = (ws / "progress.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(progress) >= 2
    result = json.loads((ws / "result.json").read_text(encoding="utf-8"))
    assert "ctr_auc" in result["metrics"] and "cvr_auc" in result["metrics"]
    import pyarrow.parquet as pq

    preds = pq.read_table(ws / "preds.parquet")
    valid = pq.read_table(paths.search_validation)
    assert preds.num_rows == valid.num_rows
    ckpts = list((ws / "checkpoints").glob("step-*.pt"))
    assert ckpts
    assert len(ckpts) <= 3


def test_features_env_changes_model(synth_50k, tmp_path: Path):
    _task, paths, _root = synth_50k
    ws_base = tmp_path / "base"
    ws_leak = tmp_path / "leak"
    a = _run_template(paths, ws_base, seed=1, features="base")
    b = _run_template(paths, ws_leak, seed=1, features="base,f_leak")
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, b.stderr
    m_a = json.loads((ws_base / "result.json").read_text())["metrics"]["cvr_auc"]
    m_b = json.loads((ws_leak / "result.json").read_text())["metrics"]["cvr_auc"]
    assert m_b - m_a > 0.2


def test_seed_changes_result(synth_50k, tmp_path: Path):
    _task, paths, _root = synth_50k
    ws1 = tmp_path / "s1"
    ws2 = tmp_path / "s2"
    ws1b = tmp_path / "s1b"
    r1 = _run_template(paths, ws1, seed=1)
    r2 = _run_template(paths, ws2, seed=2)
    r1b = _run_template(paths, ws1b, seed=1)
    assert r1.returncode == r2.returncode == r1b.returncode == 0
    m1 = json.loads((ws1 / "result.json").read_text())["metrics"]["cvr_auc"]
    m2 = json.loads((ws2 / "result.json").read_text())["metrics"]["cvr_auc"]
    m1b = json.loads((ws1b / "result.json").read_text())["metrics"]["cvr_auc"]
    assert m1 != m2
    assert m1 == m1b


@pytest.mark.parametrize(
    "mode,check",
    [
        ("crash", "exit_nonzero_traceback"),
        ("oom_cuda", "cuda_oom"),
        ("oom_host", "sigkill"),
        ("nan", "nan_progress"),
        ("hang", "still_running"),
        ("no_result", "no_result_json"),
        ("bad_schema", "missing_cvr"),
    ],
)
def test_failure_modes_observable(synth_50k, tmp_path: Path, mode: str, check: str):
    _task, paths, _root = synth_50k
    ws = tmp_path / mode
    ws.mkdir()
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
    cmd = [sys.executable, "-m", "harness.candidate.template"]
    if check == "still_running":
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            time.sleep(3)
            assert proc.poll() is None
        finally:
            proc.kill()
            proc.wait(timeout=5)
        return

    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    if check == "exit_nonzero_traceback":
        assert proc.returncode != 0
        assert "SYNTHETIC_FAIL=crash" in proc.stderr or "Traceback" in proc.stderr
    elif check == "cuda_oom":
        assert proc.returncode != 0
        assert "CUDA out of memory" in proc.stderr
    elif check == "sigkill":
        assert proc.returncode in (-9, 137)
    elif check == "nan_progress":
        assert proc.returncode == 0
        lines = (ws / "progress.jsonl").read_text().splitlines()
        assert any('"loss":NaN' in ln or '"loss":null' in ln or '"loss":nan' in ln.lower() or "NaN" in ln for ln in lines)
        # json may serialize as NaN which is non-standard; accept literal
        assert any("NaN" in ln or "nan" in ln for ln in lines)
    elif check == "no_result_json":
        assert proc.returncode == 0
        assert not (ws / "result.json").exists()
    elif check == "missing_cvr":
        assert proc.returncode == 0
        result = json.loads((ws / "result.json").read_text())
        assert "cvr_auc" not in result["metrics"]


def test_report_imports_stdlib_only():
    tree = ast.parse(REPORT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("harness")
                # top-level must be stdlib; torch is deferred inside checkpoint.save
                if getattr(node, "col_offset", 0) == 0 or True:
                    pass
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("harness")
    # Explicit: module-level imports only from stdlib
    top_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_imports.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_imports.append((node.module or "").split(".")[0])
    allowed = {"json", "os", "time", "pathlib", "annotations", "__future__"}
    for name in top_imports:
        if name in {"", "annotations"}:
            continue
        assert name in allowed or name == "pathlib"


def test_runs_under_60s_cpu(synth_50k, tmp_path: Path):
    _task, paths, _root = synth_50k
    ws = tmp_path / "ws"
    t0 = time.perf_counter()
    proc = _run_template(paths, ws)
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 60.0
