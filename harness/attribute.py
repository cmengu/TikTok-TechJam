"""Falsifiable attribution: did the declared observables move?"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Observable:
    name: str
    direction: str
    source: str  # "harness" | "candidate"


@dataclass(frozen=True)
class Claim:
    mechanism: str
    observables: list[Observable]


def _moved(o: Observable, before: float, after: float) -> bool:
    delta = float(after) - float(before)
    if o.direction in ("positive", "up"):
        return delta > 0
    if o.direction in ("negative", "down"):
        return delta < 0
    raise ValueError(f"unknown observable direction: {o.direction!r}")


def attribute(claim: Claim, before: dict, after: dict) -> str:
    if not claim.observables:
        return "unclear"
    for o in claim.observables:
        if o.name not in after or o.name not in before:
            return "unclear"
        if not _moved(o, before[o.name], after[o.name]):
            return "unclear"
    return "clear"


def observable_rows(claim: Claim, before: dict, after: dict) -> list[dict]:
    rows: list[dict] = []
    for o in claim.observables:
        b = before.get(o.name)
        a = after.get(o.name)
        moved: bool | None
        if b is None or a is None:
            moved = None
        else:
            moved = _moved(o, b, a)
        rows.append(
            {
                "name": o.name,
                "source": o.source,
                "direction": o.direction,
                "before": b,
                "after": a,
                "moved": moved,
            }
        )
    return rows


def claim_payload(claim: Claim | None, mechanism: str) -> dict:
    if claim is None:
        return {"mechanism": mechanism, "observables": []}
    return {
        "mechanism": claim.mechanism,
        "observables": [
            {"name": o.name, "source": o.source, "direction": o.direction}
            for o in claim.observables
        ],
    }


def claim_from_mapping(raw: Any, mechanism: str) -> Claim:
    if not isinstance(raw, dict):
        raise ValueError("claim must be an object")
    mech = str(raw.get("mechanism") or mechanism)
    obs_raw = raw.get("observables")
    if not isinstance(obs_raw, list) or not obs_raw:
        raise ValueError("claim.observables is required")
    observables: list[Observable] = []
    for item in obs_raw:
        if not isinstance(item, dict):
            raise ValueError("observable must be an object")
        name = item.get("name")
        direction = item.get("direction")
        source = item.get("source")
        if not name or not direction or source not in ("harness", "candidate"):
            raise ValueError(f"invalid observable: {item!r}")
        observables.append(Observable(str(name), str(direction), str(source)))
    if not any(o.source == "harness" for o in observables):
        raise ValueError("claim needs ≥1 harness-side observable")
    return Claim(mechanism=mech, observables=observables)


def claim_from_bank_row(row: dict, mechanism: str) -> Claim:
    raw = row.get("claim")
    if raw is None and "observables" in row:
        raw = {"mechanism": mechanism, "observables": row["observables"]}
    return claim_from_mapping(raw, mechanism)


def bundle_metrics(results: Iterable) -> dict[str, float]:
    """Mean of numeric metrics across results, plus derived harness observables."""
    import json
    from pathlib import Path

    collected: dict[str, list[float]] = {}
    for r in results:
        merged: dict[str, float] = {}
        for k, v in getattr(r, "metrics", {}).items():
            if isinstance(v, (int, float)):
                merged[str(k)] = float(v)
        path = getattr(r, "result_path", None)
        if path is not None:
            p = Path(path)
            if p.is_file():
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = {}
                extra = payload.get("metrics") if isinstance(payload, dict) else None
                if isinstance(extra, dict):
                    for k, v in extra.items():
                        if isinstance(v, (int, float)) and k not in merged:
                            merged[str(k)] = float(v)
        for k, v in merged.items():
            collected.setdefault(k, []).append(v)
    out = {k: sum(vs) / len(vs) for k, vs in collected.items() if vs}
    if "gauc" in out and "ndcg_at_5" in out:
        out["gauc_minus_ndcg_delta"] = out["gauc"] - out["ndcg_at_5"]
    return out


def emit_valid_pair_baseline(events, protocol) -> None:
    """Publish the valid-split pair composition before any pairwise hypothesis runs."""
    ruler = getattr(protocol, "ruler", protocol)
    if not isinstance(ruler, dict):
        return
    valid = (ruler.get("composition") or {}).get("valid") or {}
    if "no_pair_pct" not in valid:
        return
    no_pair_pct = float(valid["no_pair_pct"])
    users = valid.get("users")
    pair_forming = None
    if users is not None:
        pair_forming = float(users) * (1.0 - no_pair_pct / 100.0)
    payload: dict[str, Any] = {
        "stage": "baseline",
        "metric": "valid_pairs_per_epoch",
        "no_pair_pct": no_pair_pct,
        "summary": (
            f"valid split: {no_pair_pct}% of users form no pair "
            "(observable exists before pairwise runs)"
        ),
    }
    if users is not None:
        payload["users"] = int(users)
    if pair_forming is not None:
        payload["pair_forming_users"] = pair_forming
    events.emit("measurement", **payload)
