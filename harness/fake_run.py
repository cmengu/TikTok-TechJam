"""Phase 2: scripted schema-v1 event stream for the app."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from harness.events import EventLog
from harness.protocol import load

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocols" / "synthetic.yaml"


def _s(text: str) -> str:
    """Clamp summary to a non-empty sentence under 140 chars."""
    text = text.strip()
    if not text:
        raise ValueError("empty summary")
    return text[:139]


def _hyp(hid: str, stage: str, mechanism: str, parent: int | None = None) -> dict:
    return {
        "type": "hypothesis_queued",
        "id": hid,
        "stage": stage,
        "mechanism": mechanism,
        "parent_node": parent,
        "summary": _s(f"queued {hid} ({stage}/{mechanism})"),
    }


def _hb(worker: str, status: str, **fields) -> dict:
    return {"type": "heartbeat", "worker": worker, "status": status, **fields}


def _build_script() -> list[dict]:
    events: list[dict] = []

    # Two hypotheses per stage: features, training, objective.
    hyps = [
        _hyp("h-feat-1", "features", "target-encoding"),
        _hyp("h-feat-2", "features", "crossed-ids"),
        _hyp("h-train-1", "training", "lr-schedule"),
        _hyp("h-train-2", "training", "loss-weight"),
        _hyp("h-obj-1", "objective", "focal-loss"),
        _hyp("h-obj-2", "objective", "multi-task"),
    ]
    events.extend(hyps)

    # Node 1: draft → running → heartbeats → measurement → inconclusive.
    events.append(
        {
            "type": "node_created",
            "id": 1,
            "parent": None,
            "kind": "draft",
            "hypothesis_id": "h-feat-1",
            "summary": _s("node 1 created as draft under root"),
        }
    )
    events.append(
        {
            "type": "state_changed",
            "node": 1,
            "state": "running",
            "summary": _s("node 1 screening→running"),
        }
    )
    for i in range(40):
        events.append(_hb("w1", "busy", node=1, progress=i / 40))
    events.append(
        {
            "type": "measurement",
            "node": 1,
            "metric": "cvr_auc",
            "value": 0.512,
            "seed": 1,
            "summary": _s("node 1 measured cvr_auc=0.512 seed=1"),
        }
    )
    events.append(
        {
            "type": "verdict",
            "node": 1,
            "state": "inconclusive",
            "rung": "screen",
            "metric": "cvr_auc",
            "scores": [0.512],
            "seeds": [1],
            "band": [0.50, 0.52],
            "gpu_min": 2.5,
            "summary": _s("node 1 inconclusive: +0.012 cvr_auc inside band"),
        }
    )

    # Node 2: child of 1 → running → cuda_oom → recovery → rejected.
    events.append(
        {
            "type": "node_created",
            "id": 2,
            "parent": 1,
            "kind": "improve",
            "hypothesis_id": "h-feat-2",
            "summary": _s("node 2 created as improve under node 1"),
        }
    )
    events.append(
        {
            "type": "state_changed",
            "node": 2,
            "state": "running",
            "summary": _s("node 2 screening→running"),
        }
    )
    for i in range(20):
        events.append(_hb("w1", "busy", node=2, progress=i / 20))
    events.append(
        {
            "type": "failure",
            "node": 2,
            "class": "cuda_oom",
            "summary": _s("node 2 failed: cuda_oom on full rung"),
        }
    )
    events.append(
        {
            "type": "recovery",
            "node": 2,
            "class": "cuda_oom",
            "action": "halve_batch",
            "summary": _s("node 2 recovery: halve batch after cuda_oom"),
        }
    )
    events.append(
        {
            "type": "failure",
            "node": 2,
            "class": "stall",
            "summary": _s("node 2 failed: stall (progress watchdog)"),
        }
    )
    events.append(
        {
            "type": "recovery",
            "node": 2,
            "class": "stall",
            "action": "retry",
            "summary": _s("node 2 recovery: retry after stall"),
        }
    )
    events.append(
        {
            "type": "measurement",
            "node": 2,
            "metric": "cvr_auc",
            "value": 0.498,
            "seed": 1,
            "summary": _s("node 2 measured cvr_auc=0.498 after recovery"),
        }
    )
    events.append(
        {
            "type": "verdict",
            "node": 2,
            "state": "rejected",
            "rung": "screen",
            "metric": "cvr_auc",
            "scores": [0.498],
            "seeds": [1],
            "band": [0.50, 0.52],
            "gpu_min": 1.2,
            "summary": _s("node 2 rejected: −0.002 cvr_auc below band"),
        }
    )

    events.append(
        {
            "type": "rule_trip",
            "node": 2,
            "rule": "no_test_peek",
            "summary": _s("rule trip: no_test_peek flagged on node 2 logs"),
        }
    )
    for i, title in enumerate(
        ("Wide & Deep", "DeepFM", "NISE baseline notes"), start=1
    ):
        events.append(
            {
                "type": "research_source",
                "id": f"src-{i}",
                "title": title,
                "cost": {
                    "gpu_s": 0.0,
                    "tokens_in": 100 if i == 1 else 50,
                    "tokens_out": 40 if i == 1 else 20,
                    "slice": "researching" if i == 1 else "coding",
                },
                "summary": _s(f"research source {i}: {title}"),
            }
        )
    events.append(
        {
            "type": "cache_lookup",
            "key": "features/target-encoding",
            "hit": False,
            "summary": _s("cache miss for features/target-encoding"),
        }
    )
    events.append(
        {
            "type": "cache_lookup",
            "key": "training/lr-schedule",
            "hit": True,
            "confirmed": True,
            "summary": _s("cache hit confirmed for training/lr-schedule"),
        }
    )
    events.append(
        {
            "type": "research_source",
            "id": "src-tuning",
            "title": "tuner sweep",
            "cost": {
                "gpu_s": 0.0,
                "tokens_in": 30,
                "tokens_out": 10,
                "slice": "tuning",
            },
            "summary": _s("research source tuning: tuner sweep"),
        }
    )
    events.append(
        {
            "type": "queue_reordered",
            "order": [
                "h-train-1",
                "h-obj-1",
                "h-feat-2",
                "h-feat-1",
                "h-train-2",
                "h-obj-2",
            ],
            "summary": _s("queue reordered: training and objective floated up"),
        }
    )

    # Node 3: draft → running → replicating → promoted → submission.
    events.append(
        {
            "type": "node_created",
            "id": 3,
            "parent": 1,
            "kind": "draft",
            "hypothesis_id": "h-train-1",
            "summary": _s("node 3 created as draft under node 1"),
        }
    )
    events.append(
        {
            "type": "state_changed",
            "node": 3,
            "state": "running",
            "summary": _s("node 3 screening→running"),
        }
    )
    for i in range(50):
        events.append(_hb("w1", "busy", node=3, progress=i / 50))
    for i in range(80):
        events.append(
            {
                "type": "measurement",
                "node": 3,
                "metric": "cvr_auc",
                "value": 0.520 + (i % 10) * 0.001,
                "seed": 1,
                "summary": _s(f"node 3 screen tick {i} cvr_auc"),
            }
        )
    events.append(
        {
            "type": "measurement",
            "node": 3,
            "metric": "cvr_auc",
            "value": 0.531,
            "seed": 1,
            "summary": _s("node 3 measured cvr_auc=0.531 seed=1"),
        }
    )
    events.append(
        {
            "type": "verdict",
            "node": 3,
            "state": "replicating",
            "rung": "screen",
            "metric": "cvr_auc",
            "scores": [0.531],
            "seeds": [1],
            "band": [0.52, 0.54],
            "gpu_min": 3.0,
            "summary": _s("node 3 replicating: +0.031 cvr_auc cleared screen"),
        }
    )
    for i in range(30):
        events.append(_hb("w1", "busy", node=3, progress=0.5 + i / 60))
    events.append(
        {
            "type": "measurement",
            "node": 3,
            "metric": "cvr_auc",
            "value": 0.529,
            "seed": 2,
            "summary": _s("node 3 replicate seed=2 cvr_auc=0.529"),
        }
    )
    events.append(
        {
            "type": "verdict",
            "node": 3,
            "state": "promoted",
            "rung": "replicate",
            "metric": "cvr_auc",
            "scores": [0.529, 0.530, 0.528],
            "seeds": [1, 2, 3],
            "band": [0.52, 0.54],
            "gpu_min": 4.5,
            "summary": _s("node 3 promoted: replicate held within band"),
        }
    )
    events.append(
        {
            "type": "incumbent_changed",
            "node": 3,
            "reason": "promotion",
            "summary": _s("node 3 became incumbent (promotion)"),
        }
    )
    events.append(
        {
            "type": "measurement",
            "node": 3,
            "rung": "holdout",
            "visit": 1,
            "metric": "cvr_auc",
            "value": 0.527,
            "summary": _s("holdout visit=1 mean=0.527"),
        }
    )
    events.append(
        {
            "type": "prediction",
            "node": 3,
            "metric": "cvr_auc",
            "value": 0.527,
            "summary": _s("prediction 0.527 (η ladder accepted)"),
        }
    )
    events.append(
        {
            "type": "submission_written",
            "node": 3,
            "path": "submission/pred.csv",
            "summary": _s("submission written from promoted node 3"),
        }
    )
    events.append(
        {
            "type": "intervention",
            "kind": "pause_queue",
            "summary": _s("operator paused queue after first promotion"),
        }
    )
    events.append(_hb("w1", "idle"))
    events.append(
        {
            "type": "run_ended",
            "reason": "budget_demo",
            "summary": _s("run ended after scripted demo stream"),
        }
    )
    return events


SCRIPT: list[dict] = _build_script()


def write(run_dir: Path | str, speed: float = 20.0, instant: bool = False) -> str:
    """Emit SCRIPT through EventLog; return run id."""
    run_dir = Path(run_dir)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    run_id = run_dir.name

    protocol = load(PROTOCOL_PATH)
    log = EventLog(run_dir, run_id, protocol)
    try:
        delay = 0.0 if instant else (1.0 / speed if speed > 0 else 0.0)
        for ev in SCRIPT:
            if delay:
                time.sleep(delay)
            payload = dict(ev)
            etype = payload.pop("type")
            if etype == "heartbeat":
                worker = payload.pop("worker")
                log.heartbeat(worker, **payload)
            else:
                log.emit(etype, **payload)
    finally:
        log.close()
    return run_id
