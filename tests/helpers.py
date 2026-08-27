"""Shared test helpers (imported by test modules; fixtures stay in conftest)."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from harness.protocol import load
from harness.tasks.base import TaskPaths

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocols" / "synthetic.yaml"
CANDIDATE_DIR = ROOT / "candidate"


def placeholder_protocol(tmp_path: Path):
    raw = copy.deepcopy(yaml.safe_load(PROTOCOL.read_text()))
    raw["ruler"]["data"]["train"]["sha256"] = "0" * 63 + "1"
    raw["ruler"]["data"]["test"]["sha256"] = "0" * 63 + "2"
    raw["ruler"]["splits"]["search_validation"]["sha256"] = "0" * 63 + "3"
    raw["ruler"]["splits"]["holdout_validation"]["sha256"] = "0" * 63 + "4"
    raw["ruler"]["scoring"]["script_sha"] = "0" * 63 + "5"
    path = tmp_path / "proto.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load(path)


def stage_candidate(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    for name in ("template.py", "report.py"):
        shutil.copy2(CANDIDATE_DIR / name, workspace / name)
    return workspace / "template.py"


def run_candidate(
    paths: TaskPaths,
    ws: Path,
    *,
    seed: int = 0,
    features: str = "base",
    fail: str = "",
    epochs: int = 1,
    batch: int = 1024,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    stage_candidate(ws)
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
        [sys.executable, "template.py"],
        cwd=str(ws),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
