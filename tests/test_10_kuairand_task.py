"""Step 3: KuaiRand task adapter and metric delegation tests."""

from __future__ import annotations

import collections
import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import yaml

from harness.kit import KIT_DIR, kit_module
from harness.protocol import load as load_protocol
from harness.tasks.kuairand import KuaiRandTask, _score_script_sha

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "kuairand"
PROTOCOL_PATH = ROOT / "protocols" / "kuairand.yaml"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT / "train.csv").exists(),
    reason="KuaiRand splits not built",
)

TOL = 0.01


@pytest.fixture(scope="module")
def task():
    proto = load_protocol(PROTOCOL_PATH)
    t = KuaiRandTask()
    t.prepare(proto, ROOT / "runs" / "test-data")
    return t


def _write_preds(path: Path, labels: list[dict], scores) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_id", "user_id", "video_id", "score"])
        for i, (lab, score) in enumerate(zip(labels, scores)):
            writer.writerow([i, lab["user_id"], lab["video_id"], f"{float(score):.6g}"])


def _valid_labels(task: KuaiRandTask) -> list[dict]:
    return task._labels["search"]


def _random_preds(task: KuaiRandTask, path: Path, seed: int = 0) -> Path:
    labels = _valid_labels(task)
    rng = np.random.default_rng(seed)
    _write_preds(path, labels, rng.random(len(labels)))
    return path


def _popularity_preds(task: KuaiRandTask, path: Path) -> Path:
    kit_data = kit_module("data")
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        raw = KIT_DIR / "KuaiRand-Pure" / "data"
    splits = kit_data.load(str(raw.resolve()))
    pos, imp = collections.Counter(), collections.Counter()
    for row in splits["train"]:
        imp[row[2]] += 1
        pos[row[2]] += row[6]
    gmean = sum(pos.values()) / sum(imp.values())
    prior = 20.0
    score_fn = lambda v: (pos[v] + prior * gmean) / (imp[v] + prior) if imp[v] else gmean
    labels = _valid_labels(task)
    scores = []
    for lab in labels:
        scores.append(score_fn(lab["video_id"]))
    _write_preds(path, labels, scores)
    return path


def _fm_preds(task: KuaiRandTask, path: Path) -> Path:
    kit_data = kit_module("data")
    baseline = kit_module("baseline")
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        raw = KIT_DIR / "KuaiRand-Pure" / "data"
    splits = kit_data.load(str(raw.resolve()))
    enc, dim = kit_data.encode(splits)
    Xtr, ytr, _ = enc["train"]
    Xva, yva, uva = enc["valid"]
    m = baseline.FM(dim, k=16, lr=0.001, seed=0)
    rng = np.random.default_rng(0)
    best, state, bad = -1, None, 0
    for _ in range(40):
        idx = rng.permutation(len(ytr))
        for i in range(0, len(idx), 8192):
            m.step(Xtr[idx[i : i + 8192]], ytr[idx[i : i + 8192]])
        evaluate = kit_module("evaluate")
        p = evaluate.evaluate(uva, yva, m.predict(Xva))["primary"]
        if p > best + 1e-5:
            best, bad, state = p, 0, (m.V.copy(), m.W.copy(), m.b)
        else:
            bad += 1
            if bad >= 4:
                break
    m.V, m.W, m.b = state
    labels = _valid_labels(task)
    valid_rows = splits["valid"]
    scores = m.predict(enc["valid"][0])
    assert len(scores) == len(labels) == len(valid_rows)
    _write_preds(path, labels, scores)
    return path


def test_random_predictor_scores_near_half(task: KuaiRandTask, tmp_path: Path):
    path = _random_preds(task, tmp_path / "random.csv")
    m = task.score(path, "search")
    assert abs(m["primary"] - 0.4834) < TOL


def test_popularity_beats_random(task: KuaiRandTask, tmp_path: Path):
    random_m = task.score(_random_preds(task, tmp_path / "random.csv"), "search")
    pop_m = task.score(_popularity_preds(task, tmp_path / "pop.csv"), "search")
    fm_m = task.score(_fm_preds(task, tmp_path / "fm.csv"), "search")
    assert random_m["primary"] < pop_m["primary"] < fm_m["primary"]
    assert abs(pop_m["primary"] - 0.5807) < TOL
    assert abs(fm_m["primary"] - 0.6016) < TOL


def test_score_delegates_to_kit_evaluate(task: KuaiRandTask, tmp_path: Path):
    proto = load_protocol(PROTOCOL_PATH)
    expected = proto.ruler["scoring"]["evaluate_sha"]
    from harness.tasks.synthetic import _sha256_file

    assert _sha256_file(KIT_DIR / "evaluate.py") == expected
    path = _random_preds(task, tmp_path / "spy.csv")
    evaluate = kit_module("evaluate")
    with mock.patch.object(evaluate, "evaluate", wraps=evaluate.evaluate) as spy:
        task.score(path, "search")
        spy.assert_called_once()


def test_harness_never_scores_test(task: KuaiRandTask, tmp_path: Path):
    path = _random_preds(task, tmp_path / "test_preds.csv")
    with pytest.raises(KeyError):
        task.score(path, "test")  # type: ignore[arg-type]


def test_score_rejects_missing_ids(task: KuaiRandTask, tmp_path: Path):
    labels = _valid_labels(task)
    _write_preds(tmp_path / "short.csv", labels[:-1], np.zeros(len(labels) - 1))
    with pytest.raises(ValueError, match="count"):
        task.score(tmp_path / "short.csv", "search")


def test_score_rejects_noncontiguous_row_id(task: KuaiRandTask, tmp_path: Path):
    labels = _valid_labels(task)
    path = tmp_path / "skip.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_id", "user_id", "video_id", "score"])
        for i, lab in enumerate(labels):
            writer.writerow([i + 1, lab["user_id"], lab["video_id"], 0.5])
    with pytest.raises(ValueError, match="row_id"):
        task.score(path, "search")


def test_metric_returns_components(task: KuaiRandTask, tmp_path: Path):
    m = task.score(_random_preds(task, tmp_path / "comp.csv"), "search")
    assert "gauc" in m and "ndcg_at_5" in m and "primary" in m


def test_metric_name_comes_from_task():
    task_blind = [
        ROOT / "harness" / "measure.py",
        ROOT / "harness" / "tree.py",
        ROOT / "harness" / "agents" / "tuner.py",
        ROOT / "harness" / "runner.py",
    ]
    for path in task_blind:
        text = path.read_text(encoding="utf-8")
        assert '"cvr_auc"' not in text, path.name
        assert '"primary"' not in text, path.name

    from helpers import placeholder_protocol
    from harness.events import EventLog
    from harness.measure import Measure, SeedCache
    from harness.tasks.synthetic import SyntheticTask
    from harness.types import Cost, Node, RunResult

    tmp = ROOT / "runs" / "metric-syn"
    proto = placeholder_protocol(tmp)
    syn = SyntheticTask(n_impressions=50_000)
    syn.prepare(proto, tmp / "data")
    events = EventLog(tmp, "metric-syn", proto)
    try:
        m_syn = Measure(events, proto, band=_band(), metric=syn.metric)
        node = Node(
            id=1,
            parent=None,
            hypothesis_id="h",
            commit=None,
            state="running",
            rung="screen",
            kind="draft",
            scores={},
            seeds=[1],
            cost=Cost(gpu_s=0.0, tokens_in=0, tokens_out=0, slice="training"),
            created_seq=1,
        )
        rr = RunResult(
            node=1,
            attempt=1,
            seed=1,
            rung="screen",
            ok=True,
            metrics={"cvr_auc": 0.51},
            failure_class=None,
            stderr_tail="",
            gpu_s=1.0,
            wall_s=1.0,
            result_path=None,
            checkpoint_path=None,
        )
        v = m_syn.verdict(node, [rr], SeedCache({1: 0.5}), "screen")
        assert v.metric == "cvr_auc"
    finally:
        events.close()

    proto_k = load_protocol(PROTOCOL_PATH)
    kr = KuaiRandTask()
    kr.prepare(proto_k, ROOT / "runs" / "metric-kr" / "data")
    events_k = EventLog(ROOT / "runs" / "metric-kr", "metric-kr", proto_k)
    try:
        m_kr = Measure(events_k, proto_k, band=_band(), metric=kr.metric)
        rr_k = RunResult(
            node=1,
            attempt=1,
            seed=1,
            rung="screen",
            ok=True,
            metrics={"primary": 0.55},
            failure_class=None,
            stderr_tail="",
            gpu_s=1.0,
            wall_s=1.0,
            result_path=None,
            checkpoint_path=None,
        )
        v_k = m_kr.verdict(node, [rr_k], SeedCache({1: 0.5}), "screen")
        assert v_k.metric == "primary"
    finally:
        events_k.close()


def test_fm_submission_passes_kit_check(task: KuaiRandTask, tmp_path: Path):
    path = _fm_preds(task, tmp_path / "fm_submit.csv")
    proc = subprocess.run(
        [
            sys.executable,
            str(KIT_DIR / "submit.py"),
            str(path),
            "--check",
            "--split",
            "valid",
            "--data_dir",
            str((ROOT / "data" / "raw").resolve()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _band():
    from harness.measure import Band

    return Band(
        sigma_screen=0.01,
        sigma_full=0.008,
        sigma_pair=0.005,
        ratio=1.2,
        rho=0.5,
        sd_delta_screen=0.01,
        sd_delta_full=0.008,
        bar=0.01,
        source="fixed_pair",
        n_replicated=0,
    )


def test_script_sha_recorded_in_protocol():
    proto = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert proto["ruler"]["scoring"]["script_sha"] == _score_script_sha()


def test_reproduced_valid_is_measured():
    proto = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    reproduced = proto["ruler"]["baseline"]["reproduced"]["valid"]
    published = proto["ruler"]["baseline"]["published"]
    assert reproduced
    assert abs(reproduced["random"]["primary"] - 0.4834) < TOL
    assert abs(reproduced["popularity"]["primary"] - 0.5807) < TOL
    assert abs(reproduced["fm"]["primary"] - published["valid"]["primary"]) < TOL


def test_prepare_merges_label_and_test_digests(task: KuaiRandTask):
    path = DATA_ROOT / "harness_only" / "digests.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "train",
        "test",
        "search",
        "holdout",
        "script",
        "search_labels",
        "oracle_labels",
        "test_features",
    ):
        assert key in data, key
        assert len(data[key]) == 64
