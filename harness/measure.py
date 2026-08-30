"""Phase 5: noise band, ladder, leak audit, promotion verdicts."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from harness.events import EventLog
from harness.protocol import Protocol
from harness.types import Node, Rung, RunResult, State, Verdict

# Redline §6 Ladder: refuse to search if sigma_full exceeds this
SIGMA_UNSTABLE = 0.020
# Redline §6 Ladder: screen — delta at or below this → rejected
SCREEN_REJECT_DELTA = -0.010
# Redline §6 Ladder: screen — delta ≥ this × sd_delta_screen → replicating
SCREEN_ADVANCE_SD = 1.0
# Redline §6 Ladder: replicate — bar never below this
PROMOTE_FLOOR = 0.010
# Redline §6 Ladder: replicate — 1.645 / √3 — one-sided known-σ test, α = 0.05, k = 3
PROMOTE_Z_OVER_SQRT_K = 0.95
# Redline §6 Ladder: seeds on the full rung; all three must be > 0
REPLICATE_K = 3
# Redline §6 Ladder: mean delta ≥ this × sd_delta_full → leak audit before any promotion
LEAK_TRIGGER_BANDS = 5.0
# Redline §6 Ladder: single-feature AUC above this trips R3
LEAK_SINGLE_FEATURE_AUC = 0.90
# Redline §6 Ladder: holdout — report a new number only if ≥ best + eta
LADDER_ETA = 0.005
# Redline §6 Ladder: holdout visits per run
HOLDOUT_VISITS_MAX = 12
# Redline §6 Ladder: candidate-side holdout seeds; incumbent from cache
HOLDOUT_SEEDS = 3
# Redline §6 Ladder: third inconclusive → retired
INCONCLUSIVE_REVISITS = 2
# Redline §6 Ladder: multiplier applied to the hypothesis on requeue
INCONCLUSIVE_PRIORITY = 0.5
# Redline §6 Ladder: replicated candidates before rho is re-estimated
RHO_REFRESH_AFTER = 3
# Redline §6 Ladder: stall threshold as multiple of sd (consumed by phase 6)
STALL_SD_MULT = 2.0

LEAK_RULE_GAIN = "leak_implausible_gain"
LEAK_RULE_FEATURE = "R3_single_feature"


@dataclass
class Band:
    sigma_screen: float
    sigma_full: float
    sigma_pair: float
    ratio: float
    rho: float
    sd_delta_screen: float
    sd_delta_full: float
    bar: float
    source: Literal["fixed_pair", "refreshed"]
    n_replicated: int


@dataclass
class Delta:
    value: float
    rung: Rung


@dataclass
class HoldoutReport:
    visit: int
    seeds: list[int]
    candidate_scores: list[float]
    incumbent_scores: list[float]
    delta_mean: float
    accepted: bool
    best_reported: float


class CalibrationError(Exception):
    """Raised when calibrated sigma_full exceeds the §6 instability gate."""


class RungMismatch(Exception):
    """Raised when a smoke/screen delta is mixed into a replicate verdict."""


class MissingIncumbentSeed(Exception):
    """Raised when the incumbent cache has no score for a required seed."""


class HoldoutBudgetExceeded(Exception):
    """Raised on the third holdout_report call before any run is launched."""


class SeedCache:
    """Per-seed incumbent scores for paired deltas."""

    def __init__(self, scores: dict[int, float]) -> None:
        self._scores = {int(k): float(v) for k, v in scores.items()}

    def get(self, seed: int) -> float:
        if int(seed) not in self._scores:
            raise MissingIncumbentSeed(int(seed))
        return self._scores[int(seed)]

    def as_dict(self) -> dict[int, float]:
        return dict(self._scores)


def _sd_delta(sigma: float, rho: float) -> float:
    return float(sigma) * math.sqrt(2.0 * (1.0 - float(rho)))


def _bar_from(sd_delta_full: float) -> float:
    return max(PROMOTE_FLOOR, PROMOTE_Z_OVER_SQRT_K * float(sd_delta_full))


def _band_payload(band: Band) -> dict[str, Any]:
    return asdict(band)


def calibrate(
    screen_per_seed: list[float],
    full_per_seed: list[float],
    fixed_seed_pair: tuple[float, float],
) -> Band:
    if len(screen_per_seed) < 2:
        raise CalibrationError("need ≥2 screen seeds to estimate sigma_screen")
    if len(full_per_seed) < 2:
        raise CalibrationError("need ≥2 full seeds to estimate sigma_full")
    sigma_screen = statistics.stdev(screen_per_seed)
    sigma_full = statistics.stdev(full_per_seed)
    if sigma_full > SIGMA_UNSTABLE:
        raise CalibrationError(
            f"sigma_full={sigma_full:.4f} exceeds SIGMA_UNSTABLE={SIGMA_UNSTABLE}"
        )
    a, b = fixed_seed_pair
    sigma_pair = abs(float(a) - float(b)) / math.sqrt(2.0)
    rho = 0.5 if sigma_pair > 0.5 * sigma_screen else 0.8
    sd_screen = _sd_delta(sigma_screen, rho)
    sd_full = _sd_delta(sigma_full, rho)
    ratio = sigma_full / sigma_screen if sigma_screen > 0 else float("inf")
    return Band(
        sigma_screen=sigma_screen,
        sigma_full=sigma_full,
        sigma_pair=sigma_pair,
        ratio=ratio,
        rho=rho,
        sd_delta_screen=sd_screen,
        sd_delta_full=sd_full,
        bar=_bar_from(sd_full),
        source="fixed_pair",
        n_replicated=0,
    )


def refresh_rho(band: Band, per_seed_deltas: list[list[float]]) -> Band:
    vars_: list[float] = []
    for deltas in per_seed_deltas:
        if len(deltas) >= 2:
            vars_.append(statistics.pvariance(deltas))
    if not vars_:
        return replace(band, source="refreshed")
    mean_var = statistics.mean(vars_)
    denom = 2.0 * (band.sigma_full**2)
    if denom <= 0:
        rho = band.rho
    else:
        rho = 1.0 - mean_var / denom
    rho = max(0.0, min(0.9, float(rho)))
    sd_screen = _sd_delta(band.sigma_screen, rho)
    sd_full = _sd_delta(band.sigma_full, rho)
    return Band(
        sigma_screen=band.sigma_screen,
        sigma_full=band.sigma_full,
        sigma_pair=band.sigma_pair,
        ratio=band.ratio,
        rho=rho,
        sd_delta_screen=sd_screen,
        sd_delta_full=sd_full,
        bar=_bar_from(sd_full),
        source="refreshed",
        n_replicated=band.n_replicated,
    )


def screen_verdict(
    delta: float, band: Band
) -> Literal["rejected", "replicating", "inconclusive"]:
    if delta <= SCREEN_REJECT_DELTA:
        return "rejected"
    if delta >= SCREEN_ADVANCE_SD * band.sd_delta_screen:
        return "replicating"
    return "inconclusive"


def promote_bar(band: Band) -> float:
    return _bar_from(band.sd_delta_full)


def replicate_verdict(
    deltas: list[Delta], band: Band
) -> Literal["pass", "fail_sign", "fail_mean"]:
    for d in deltas:
        if d.rung not in ("full", "replicate"):
            raise RungMismatch(
                f"replicate_verdict refuses rung={d.rung!r}; expected full|replicate"
            )
    values = [d.value for d in deltas]
    if len(values) != REPLICATE_K or any(v <= 0 for v in values):
        return "fail_sign"
    if statistics.mean(values) < promote_bar(band):
        return "fail_mean"
    return "pass"


def leak_audit(
    mean_delta: float,
    band: Band,
    single_feature_aucs: dict[str, float],
) -> list[str]:
    trips: list[str] = []
    if mean_delta >= LEAK_TRIGGER_BANDS * band.sd_delta_full:
        trips.append(LEAK_RULE_GAIN)
    for name, auc in single_feature_aucs.items():
        if float(auc) > LEAK_SINGLE_FEATURE_AUC:
            trips.append(LEAK_RULE_FEATURE)
            break
    return trips


def ladder_accepts(
    best_reported: float, new_holdout: float, eta: float = LADDER_ETA
) -> bool:
    return float(new_holdout) >= float(best_reported) + float(eta)


def inconclusive_next(
    prior_inconclusives: int,
) -> Literal["requeue", "retire"]:
    if int(prior_inconclusives) >= INCONCLUSIVE_REVISITS:
        return "retire"
    return "requeue"


def combine_inconclusive(a: Verdict, b: Verdict) -> Literal["re_measure"]:
    del a, b
    return "re_measure"


class Measure:
    def __init__(
        self,
        events: EventLog,
        protocol: Protocol,
        band: Band | None,
        *,
        metric: str,
    ) -> None:
        self.events = events
        self.protocol = protocol
        self.band = band
        self.metric = metric
        self._holdout_visits = 0
        self._replicate_deltas: list[list[float]] = []
        self._rho_refreshed = False
        self._timeout_s = float(
            (protocol.run or {}).get("measure_timeout_s", 600.0)
            if hasattr(protocol, "run")
            else 600.0
        )

    @property
    def holdout_visits(self) -> int:
        return self._holdout_visits

    def calibrate_from_runs(
        self,
        runner,
        baseline_node: Node,
        screen_seeds: list[int] | None = None,
        full_seeds: list[int] | None = None,
        fixed_pair: list[int] | None = None,
    ) -> Band:
        screen_seeds = list(screen_seeds or [1, 2, 3, 4, 5])
        full_seeds = list(full_seeds or [1, 2, 3])
        fixed_pair = list(fixed_pair or [1, 1])
        timeout_s = float(
            getattr(runner, "run_cfg", {}).get("timeout_s", self._timeout_s)
        )

        screen_scores: list[float] = []
        for seed in screen_seeds:
            result = runner.run(
                baseline_node, "screen", seed=seed, timeout_s=timeout_s
            )
            if not result.ok:
                raise CalibrationError(
                    f"screen seed {seed} failed: {result.failure_class}"
                )
            screen_scores.append(float(result.metrics[self.metric]))

        pair_scores: list[float] = []
        for seed in fixed_pair:
            result = runner.run(
                baseline_node, "screen", seed=seed, timeout_s=timeout_s
            )
            if not result.ok:
                raise CalibrationError(
                    f"fixed-pair seed {seed} failed: {result.failure_class}"
                )
            pair_scores.append(float(result.metrics[self.metric]))
        if len(pair_scores) != 2:
            raise CalibrationError("fixed_pair must yield exactly two scores")

        full_scores: list[float] = []
        for seed in full_seeds:
            result = runner.run(
                baseline_node, "full", seed=seed, timeout_s=timeout_s
            )
            if not result.ok:
                raise CalibrationError(
                    f"full seed {seed} failed: {result.failure_class}"
                )
            full_scores.append(float(result.metrics[self.metric]))

        band = calibrate(
            screen_scores, full_scores, (pair_scores[0], pair_scores[1])
        )
        self.band = band
        self.events.emit(
            "measurement",
            stage="calibrate",
            metric=self.metric,
            band=_band_payload(band),
            producer="measure",
            summary=(
                f"calibrated band bar={band.bar:.4f} "
                f"σ_full={band.sigma_full:.4f} ρ={band.rho}"
            ),
        )
        return band

    def verdict(
        self,
        node: Node,
        results: list[RunResult],
        incumbent: SeedCache,
        rung: Rung,
        attribution: Literal["clear", "unclear", None] = None,
        single_feature_aucs: dict[str, float] | None = None,
        gpu_min: float | None = None,
        oracle_delta: float | None = None,
        on_promote_oracle: Any = None,
    ) -> Verdict:
        if self.band is None:
            raise CalibrationError("Measure.verdict requires a calibrated Band")
        if rung == "smoke":
            raise RungMismatch("verdict() refuses smoke; smoke is runner-only")
        if rung == "holdout":
            raise RungMismatch("holdout is not a ladder rung; use holdout_report()")

        band = self.band
        seeds = [r.seed for r in results]
        scores = [float(r.metrics.get(self.metric, float("nan"))) for r in results]
        deltas = [
            float(score) - incumbent.get(seed)
            for seed, score in zip(seeds, scores, strict=True)
        ]

        rule_trips: list[str] = []
        state: State
        reason: str
        delta_mean: float | None

        if rung == "screen":
            if len(deltas) != 1:
                raise ValueError("screen verdict expects exactly one paired result")
            delta_mean = deltas[0]
            decision = screen_verdict(delta_mean, band)
            state = decision  # rejected | replicating | inconclusive
            reason = f"screen {decision}: Δ={delta_mean:+.4f}"
        elif rung == "replicate":
            tagged = [Delta(value=d, rung="replicate") for d in deltas]
            decision = replicate_verdict(tagged, band)
            delta_mean = statistics.mean(deltas) if deltas else None
            self._replicate_deltas.append(list(deltas))
            band = replace(band, n_replicated=band.n_replicated + 1)
            self.band = band

            if (
                delta_mean is not None
                and delta_mean >= LEAK_TRIGGER_BANDS * band.sd_delta_full
            ):
                rule_trips = leak_audit(
                    delta_mean, band, single_feature_aucs or {}
                )
                for rule_id in rule_trips:
                    self.events.emit(
                        "rule_trip",
                        node=node.id,
                        rule=rule_id,
                        summary=f"node {node.id} rule_trip {rule_id}",
                    )

            if rule_trips:
                state = "leaked"
                reason = f"replicate leaked: {','.join(rule_trips)}"
            elif decision == "pass":
                if attribution == "unclear":
                    state = "inconclusive"
                    reason = "replicate pass but attribution unclear"
                else:
                    # attribution "clear" or None → promote
                    state = "promoted"
                    reason = f"replicate pass: mean Δ={delta_mean:+.4f} ≥ bar={band.bar:.4f}"
            elif decision == "fail_sign":
                state = "rejected"
                reason = "replicate fail_sign"
            else:
                state = "rejected"
                reason = "replicate fail_mean"
        else:
            raise RungMismatch(f"unsupported verdict rung={rung!r}")

        sd = band.sd_delta_screen if rung == "screen" else band.sd_delta_full
        verdict = Verdict(
            node=node.id,
            rung=rung,
            state=state,
            metric=self.metric,
            delta_mean=delta_mean,
            delta_per_seed=deltas,
            band=(-sd, sd),
            reason=reason,
            rule_trips=rule_trips,
        )
        payload: dict[str, Any] = {
            "node": node.id,
            "state": state,
            "metric": self.metric,
            "scores": scores,
            "seeds": seeds,
            "band": _band_payload(band),
            "rung": rung,
            "delta_mean": delta_mean,
            "delta_per_seed": deltas,
            "summary": reason,
        }
        if attribution is not None:
            payload["attribution"] = attribution
        if gpu_min is not None:
            payload["gpu_min"] = float(gpu_min)
        if (
            state == "promoted"
            and oracle_delta is None
            and on_promote_oracle is not None
        ):
            try:
                oracle_delta = on_promote_oracle()
            except (HoldoutBudgetExceeded, RuntimeError) as exc:
                self.events.emit(
                    "failure",
                    node=node.id,
                    summary=f"oracle failed: {exc}",
                    **{"class": "oracle_failed"},
                )
                oracle_delta = None
        if oracle_delta is not None:
            payload["oracle_delta"] = float(oracle_delta)
        if rule_trips:
            payload["rule_trips"] = rule_trips
        payload["producer"] = "measure"
        self.events.emit("verdict", **payload)

        if state == "promoted":
            self.events.emit(
                "incumbent_changed",
                node=node.id,
                reason="promotion",
                summary=f"node {node.id} became incumbent (promotion)",
            )
        return verdict

    def holdout_report(
        self,
        node: Node,
        runner,
        incumbent: SeedCache,
        best_reported: float,
    ) -> HoldoutReport:
        if self._holdout_visits >= HOLDOUT_VISITS_MAX:
            raise HoldoutBudgetExceeded(
                f"holdout visits already at max {HOLDOUT_VISITS_MAX}"
            )
        timeout_s = float(
            getattr(runner, "run_cfg", {}).get("timeout_s", self._timeout_s)
        )
        seeds = list(range(1, HOLDOUT_SEEDS + 1))
        # Count the visit before launching so a crash mid-visit still consumes budget.
        self._holdout_visits += 1
        visit = self._holdout_visits

        candidate_scores: list[float] = []
        incumbent_scores: list[float] = []
        for seed in seeds:
            result = runner.run(
                node, "holdout", seed=seed, timeout_s=timeout_s
            )
            if not result.ok:
                raise RuntimeError(
                    f"holdout seed {seed} failed: {result.failure_class}"
                )
            cand = float(result.metrics[self.metric])
            inc = incumbent.get(seed)
            candidate_scores.append(cand)
            incumbent_scores.append(inc)

        delta_mean = statistics.mean(
            c - i for c, i in zip(candidate_scores, incumbent_scores, strict=True)
        )
        # Reported number is the candidate mean holdout score (not a delta).
        new_holdout = statistics.mean(candidate_scores)
        accepted = ladder_accepts(best_reported, new_holdout)
        next_best = new_holdout if accepted else best_reported

        self.events.emit(
            "measurement",
            node=node.id,
            rung="holdout",
            visit=visit,
            metric=self.metric,
            value=new_holdout,
            delta_mean=delta_mean,
            seeds=seeds,
            producer="measure",
            summary=f"holdout visit={visit} mean={new_holdout:.4f}",
        )
        if accepted:
            self.events.emit(
                "prediction",
                node=node.id,
                metric=self.metric,
                value=new_holdout,
                best_reported=next_best,
                band=_band_payload(self.band) if self.band else None,
                producer="measure",
                summary=f"prediction {new_holdout:.4f} (η ladder accepted)",
            )
        return HoldoutReport(
            visit=visit,
            seeds=seeds,
            candidate_scores=candidate_scores,
            incumbent_scores=incumbent_scores,
            delta_mean=delta_mean,
            accepted=accepted,
            best_reported=next_best,
        )

    def maybe_refresh(self) -> Band | None:
        if self.band is None:
            return None
        if self._rho_refreshed:
            return None
        if self.band.n_replicated < RHO_REFRESH_AFTER:
            return None
        if len(self._replicate_deltas) < RHO_REFRESH_AFTER:
            return None
        refreshed = refresh_rho(
            self.band, self._replicate_deltas[:RHO_REFRESH_AFTER]
        )
        self.band = refreshed
        self._rho_refreshed = True
        self.events.emit(
            "measurement",
            stage="calibrate",
            refreshed=True,
            metric=self.metric,
            band=_band_payload(refreshed),
            producer="measure",
            summary=(
                f"refreshed ρ={refreshed.rho:.3f} bar={refreshed.bar:.4f} "
                f"after {RHO_REFRESH_AFTER} replicated"
            ),
        )
        return refreshed
