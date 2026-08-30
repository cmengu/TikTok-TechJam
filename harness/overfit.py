"""Overfitting monitors — pure folds over a list of event dicts."""

from __future__ import annotations

import math
import statistics


def _promotions(events: list[dict]) -> list[dict]:
    return [
        e
        for e in events
        if e.get("type") == "verdict" and e.get("state") == "promoted"
    ]


def oracle_gap(events: list[dict]) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for e in _promotions(events):
        if "oracle_delta" not in e or e.get("delta_mean") is None:
            continue
        if e["oracle_delta"] is None:
            continue
        out.append((int(e["node"]), float(e["delta_mean"]) - float(e["oracle_delta"])))
    return out


def gap_alarm(events: list[dict]) -> bool:
    gaps = [x for _, x in oracle_gap(events)]
    return len(gaps) >= 3 and gaps[-1] > gaps[-2] > gaps[-3]


def seed_consistency(delta_per_seed: list[float]) -> float:
    if not delta_per_seed:
        return 0.0
    mean = statistics.mean(delta_per_seed)
    return sum((d > 0) == (mean > 0) for d in delta_per_seed) / len(delta_per_seed)


def _ranks(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return None
    return num / (dx * dy)


def split_rank_corr(events: list[dict]) -> float | None:
    promos = [
        e
        for e in _promotions(events)
        if e.get("delta_mean") is not None and e.get("oracle_delta") is not None
    ]
    if len(promos) < 3:
        return None
    xs = [float(e["delta_mean"]) for e in promos]
    ys = [float(e["oracle_delta"]) for e in promos]
    return _pearson(_ranks(xs), _ranks(ys))


def ladder_queries(events: list[dict]) -> int:
    return len(_promotions(events))


def headline(events: list[dict]) -> tuple[float | None, float | None]:
    """Return (primary, spread) folded from the log. Spread is None if n < 2."""
    primary: float | None = None
    spread: float | None = None
    for e in events:
        if e.get("type") == "prediction" and e.get("value") is not None:
            primary = float(e["value"])
    promos = _promotions(events)
    if promos:
        last = promos[-1]
        scores = last.get("scores") or []
        if scores:
            nums = [float(s) for s in scores]
            if primary is None:
                primary = statistics.mean(nums)
            if len(nums) >= 2:
                spread = statistics.stdev(nums)
        elif last.get("delta_mean") is not None and primary is None:
            primary = float(last["delta_mean"])
    return primary, spread


def seed_consistency_by_node(events: list[dict]) -> list[tuple[int, float]]:
    rows: list[tuple[int, float]] = []
    for e in _promotions(events):
        deltas = e.get("delta_per_seed") or []
        if not deltas:
            continue
        rows.append((int(e["node"]), seed_consistency([float(d) for d in deltas])))
    return rows
