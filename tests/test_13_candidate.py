"""Step 6: KuaiRand FM candidate template tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.protocol import load as load_protocol
from harness.tasks.kuairand import KuaiRandTask
from helpers import run_candidate

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocols" / "kuairand.yaml"

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
    import json

    lines = (ROOT / "candidate" / "rules.jsonl").read_text().strip().splitlines()
    assert len(lines) == 9
    for line in lines:
        json.loads(line)
