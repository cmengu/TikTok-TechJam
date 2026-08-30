"""Shared dataclasses and vocabularies — the two-person seam (phase 0)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Stage = Literal["data", "features", "objective", "architecture", "training", "ensemble"]
State = Literal[
    "screening",
    "running",
    "replicating",
    "promoted",
    "inconclusive",
    "rejected",
    "retired",
    "leaked",
    "debugging",
]
Rung = Literal["smoke", "screen", "full", "replicate", "holdout"]

EVENT_TYPES = (
    "run_started",
    "node_created",
    "state_changed",
    "heartbeat",
    "measurement",
    "verdict",
    "failure",
    "recovery",
    "rule_trip",
    "research_source",
    "cache_lookup",
    "hypothesis_queued",
    "queue_reordered",
    "submission_run",
    "submission_written",
    "intervention",
    "run_ended",
    "incumbent_changed",
    "prediction",
)
# Phase 5 added incumbent_changed + prediction (Plan_delta §1; no schema bump).
STATES = (
    "screening",
    "running",
    "replicating",
    "promoted",
    "inconclusive",
    "rejected",
    "retired",
    "leaked",
    "debugging",
)


@dataclass
class Cost:
    gpu_s: float
    tokens_in: int
    tokens_out: int
    slice: Literal["researching", "coding", "training", "tuning"]


@dataclass
class Hypothesis:
    id: str
    stage: Stage
    mechanism: str  # family = f"{stage}/{mechanism}"
    description: str
    citation: str  # "no prior" when none
    expected_gain: float
    expected_gpu_h: float
    parent_node: int | None
    patch: Path | None  # hand-written patches only (phase 6)


@dataclass
class Node:
    id: int
    parent: int | None
    hypothesis_id: str
    commit: str | None
    state: State
    rung: Rung
    kind: Literal["draft", "improve", "debug", "ablate", "trial", "ensemble"]
    scores: dict[str, list[float]]  # metric -> per-seed scores, parallel to seeds
    seeds: list[int]
    cost: Cost
    created_seq: int


@dataclass
class RunResult:
    node: int
    attempt: int
    seed: int
    rung: Rung
    ok: bool
    metrics: dict[str, float]
    failure_class: str | None
    stderr_tail: str
    gpu_s: float
    wall_s: float
    result_path: Path | None
    checkpoint_path: Path | None


@dataclass
class Verdict:
    node: int
    rung: Rung
    state: State
    metric: str
    delta_mean: float | None
    delta_per_seed: list[float]
    band: tuple[float, float]
    reason: str  # becomes the event's summary
    rule_trips: list[str]
