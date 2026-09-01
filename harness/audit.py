"""Phase 9: read-only projections over the event log."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class MixedProtocolError(ValueError):
    """Raised when events carry more than one protocol_hash."""


_SLICES = ("researching", "coding", "training", "tuning")


def _parse_ts(t: str) -> float:
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    return datetime.fromisoformat(t).timestamp()


def assert_single_protocol(events: list[dict]) -> None:
    hashes = {ev.get("protocol_hash") for ev in events if ev.get("protocol_hash")}
    if len(hashes) > 1:
        raise MixedProtocolError(
            f"refusing to pool {len(hashes)} protocol hashes: {sorted(hashes)}"
        )


def replication_pairs(events: list[dict]) -> list[dict]:
    """Per-node replication deltas: screen vs full, 1 vs many seeds, search vs holdout."""
    assert_single_protocol(events)
    by_node: dict[int, dict[str, Any]] = {}

    for ev in events:
        if ev.get("type") == "verdict":
            node = int(ev["node"])
            rung = ev.get("rung")
            scores = ev.get("scores") or []
            seeds = ev.get("seeds") or []
            if not scores:
                continue
            bucket = by_node.setdefault(
                node,
                {
                    "screen": None,
                    "full_mean": None,
                    "one_seed": None,
                    "many_mean": None,
                    "searchval": None,
                },
            )
            mean = sum(float(s) for s in scores) / len(scores)
            if rung == "screen":
                bucket["screen"] = mean
                if len(scores) == 1:
                    bucket["one_seed"] = float(scores[0])
            elif rung in ("full", "replicate"):
                bucket["full_mean"] = mean
                bucket["many_mean"] = mean
                if bucket["one_seed"] is None and len(scores) == 1:
                    bucket["one_seed"] = float(scores[0])
                bucket["searchval"] = mean
        elif ev.get("type") == "measurement" and ev.get("rung") == "holdout":
            node = int(ev["node"])
            bucket = by_node.setdefault(
                node,
                {
                    "screen": None,
                    "full_mean": None,
                    "one_seed": None,
                    "many_mean": None,
                    "searchval": None,
                },
            )
            bucket["holdout"] = float(ev["value"])

    rows: list[dict] = []
    for node, data in sorted(by_node.items()):
        screen = data.get("screen")
        full_mean = data.get("full_mean")
        one_seed = data.get("one_seed")
        many_mean = data.get("many_mean")
        searchval = data.get("searchval")
        holdout = data.get("holdout")

        screen_vs_full = None
        if screen is not None and full_mean is not None:
            screen_vs_full = float(full_mean) - float(screen)

        one_vs_many_seeds = None
        if one_seed is not None and many_mean is not None:
            one_vs_many_seeds = float(many_mean) - float(one_seed)

        searchval_vs_holdout = None
        if searchval is not None and holdout is not None:
            searchval_vs_holdout = float(searchval) - float(holdout)

        pair_count = sum(
            x is not None
            for x in (screen_vs_full, one_vs_many_seeds, searchval_vs_holdout)
        )
        if pair_count == 0:
            if data.get("screen") is not None:
                rows.append(
                    {
                        "node": node,
                        "screen_vs_full": None,
                        "one_vs_many_seeds": None,
                        "searchval_vs_holdout": None,
                    }
                )
            continue

        rows.append(
            {
                "node": node,
                "screen_vs_full": screen_vs_full,
                "one_vs_many_seeds": one_vs_many_seeds,
                "searchval_vs_holdout": searchval_vs_holdout,
            }
        )
    return rows


def cost_by_slice(events: list[dict]) -> dict:
    """Sum token costs and GPU-hours per slice from cost fields and verdict gpu_min."""
    assert_single_protocol(events)
    out: dict[str, dict[str, float]] = {
        s: {"tokens_in": 0.0, "tokens_out": 0.0, "gpu_h": 0.0} for s in _SLICES
    }
    for ev in events:
        cost = ev.get("cost")
        if isinstance(cost, dict):
            sl = cost.get("slice")
            if sl in out:
                out[sl]["tokens_in"] += float(cost.get("tokens_in", 0))
                out[sl]["tokens_out"] += float(cost.get("tokens_out", 0))
                out[sl]["gpu_h"] += float(cost.get("gpu_s", 0)) / 3600.0
        if ev.get("type") == "verdict" and ev.get("gpu_min") is not None:
            out["training"]["gpu_h"] += float(ev["gpu_min"]) / 60.0
    return out


def reliability(events: list[dict]) -> dict:
    """Failure/recovery counts, submission timing, unattended gap, rule trips."""
    assert_single_protocol(events)
    failures_by_class: dict[str, int] = {}
    recoveries: dict[str, int] = {"ok": 0, "failed": 0}
    rule_trips = 0
    started_ts: float | None = None
    ended_ts: float | None = None
    first_submission_ts: float | None = None
    intervention_ts: list[float] = []

    for ev in events:
        etype = ev.get("type")
        ts = _parse_ts(ev["t"]) if ev.get("t") else None
        if etype == "run_started" and ts is not None:
            started_ts = ts
        elif etype == "run_ended" and ts is not None:
            ended_ts = ts
        elif etype == "failure":
            cls = str(ev.get("class", "unknown"))
            failures_by_class[cls] = failures_by_class.get(cls, 0) + 1
        elif etype == "recovery":
            action = str(ev.get("action", ""))
            # patch_retried / fullfile_fallback are the coder's own recovery
            # ladder (throughput batch): the action was taken, count it ok.
            if action in ("retry", "halve_batch", "patch_retried", "fullfile_fallback"):
                recoveries["ok"] += 1
            else:
                recoveries["failed"] += 1
        elif etype == "rule_trip":
            rule_trips += 1
        elif etype == "submission_written" and ts is not None:
            if first_submission_ts is None:
                first_submission_ts = ts
        elif etype == "intervention" and ts is not None:
            intervention_ts.append(ts)

    time_to_first_valid_submission_s = None
    if started_ts is not None and first_submission_ts is not None:
        time_to_first_valid_submission_s = first_submission_ts - started_ts

    longest_unattended_s = 0.0
    if started_ts is not None and ended_ts is not None:
        if not intervention_ts:
            longest_unattended_s = ended_ts - started_ts
        else:
            gaps = [intervention_ts[0] - started_ts]
            gaps.extend(
                intervention_ts[i + 1] - intervention_ts[i]
                for i in range(len(intervention_ts) - 1)
            )
            gaps.append(ended_ts - intervention_ts[-1])
            longest_unattended_s = max(gaps)

    return {
        "failures_by_class": failures_by_class,
        "recoveries": recoveries,
        "time_to_first_valid_submission_s": time_to_first_valid_submission_s,
        "longest_unattended_s": longest_unattended_s,
        "rule_trips": rule_trips,
    }
