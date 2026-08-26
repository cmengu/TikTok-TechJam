"""Phase 5: noise band, ladder, leak audit, promotion verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from harness.events import EventLog
from harness.protocol import Protocol
from harness.types import Node, Rung, RunResult, Verdict

# Thresholds filled in phase 5 from Harness Decisions §6 — not invented here.


@dataclass
class Band:
    sigma: float
    sigma_pair: float
    rho_col: Literal[0.5, 0.8]
    sd_delta: float
    lo: float
    hi: float


class CalibrationError(Exception):
    """Raised when calibrated sigma exceeds the §6 instability gate."""


def calibrate(
    baseline_per_seed: list[float],
    fixed_seed_pair: tuple[float, float],
) -> Band:
    raise NotImplementedError


def screen_verdict(
    delta: float, band: Band
) -> Literal["rejected", "replicating", "inconclusive"]:
    raise NotImplementedError


def replicate_verdict(
    deltas: list[float], band: Band
) -> tuple[Literal["provisional", "pass", "fail", "buy_more"], float]:
    raise NotImplementedError


def bh_select(pvalues: dict[int, float], q: float = 0.10) -> set[int]:
    raise NotImplementedError


def checkpoint_sensitivity(deltas_at: dict[float, float], band: Band) -> bool:
    raise NotImplementedError


def holdout_confirm(
    val_c: float,
    hold_c: float,
    val_b: float,
    hold_b: float,
    band: Band,
) -> Literal["promoted", "overfit", "one_more_seed", "shift"]:
    raise NotImplementedError


def ladder_accepts(best_reported: float, new_holdout: float, eta: float = 0.005) -> bool:
    raise NotImplementedError


def leak_audit(
    delta: float,
    band: Band,
    single_feature_aucs: dict[str, float],
) -> list[str]:
    raise NotImplementedError


def combine_inconclusive(a: Verdict, b: Verdict) -> Literal["re_measure"]:
    raise NotImplementedError


class Measure:
    def __init__(
        self, events: EventLog, protocol: Protocol, band: Band | None
    ) -> None:
        raise NotImplementedError

    def calibrate_from_runs(
        self,
        runner,
        baseline_node: Node,
        seeds: list[int] | None = None,
        fixed_pair: list[int] | None = None,
    ) -> Band:
        raise NotImplementedError

    def verdict(
        self,
        node: Node,
        results: list[RunResult],
        incumbent_scores: list[float],
        rung: Rung,
        holdout=None,
    ) -> Verdict:
        raise NotImplementedError
