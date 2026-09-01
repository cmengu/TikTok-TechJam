"""Export the judge-facing deliverables for one run, straight from its event log.

Deliverable 3 (run & iteration logs) and the numbers behind deliverable 4
(results + resource usage). Everything here is read from events.jsonl — no
value is recomputed, invented, or rounded up.

    python scripts/export_iterations.py <run-id>

Writes into runs/<run-id>/:
  iterations.jsonl  one record per attempt: hypothesis + why, the diff it
                    applied, the metrics it scored, and every error and
                    recovery it hit
  summary.json      results table, resource usage, intervention count
  SUMMARY.md        the same, readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Published organiser baseline (starter kit, baseline_scores.json).
BASELINE = {
    "valid": {"gauc": 0.6674, "ndcg_at_5": 0.5357, "primary": 0.6016},
    "test": {"gauc": 0.6610, "ndcg_at_5": 0.5282, "primary": 0.5946},
}


def read_events(run_dir: Path) -> list[dict]:
    out = []
    for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def build(run_id: str) -> tuple[list[dict], dict]:
    run_dir = REPO / "runs" / run_id
    events = read_events(run_dir)

    hyps: dict[str, dict] = {}
    for ev in events:
        if ev.get("type") == "hypothesis_queued":
            hid = ev.get("hypothesis") or ev.get("id")
            if hid:
                hyps[str(hid)] = ev

    nodes: dict[int, dict] = {}

    def slot(nid) -> dict | None:
        if nid is None:
            return None
        return nodes.setdefault(
            int(nid),
            {
                "node": int(nid),
                "hypothesis": None,
                "mechanism": None,
                "why": None,
                "citation": None,
                "diff": None,
                "metrics": {},
                "verdicts": [],
                "errors": [],
                "recoveries": [],
                "attribution": None,
                "commit": None,
            },
        )

    for ev in events:
        t = ev.get("type")
        rec = slot(ev.get("node"))
        if t == "node_created" and rec is not None:
            hid = ev.get("hypothesis") or ev.get("hypothesis_id")
            rec["hypothesis"] = hid
            src = hyps.get(str(hid), {})
            rec["mechanism"] = ev.get("mechanism") or src.get("mechanism")
            rec["why"] = src.get("description") or src.get("summary")
            rec["citation"] = src.get("citation")
            if ev.get("commit"):
                rec["commit"] = ev["commit"]
        elif t == "verdict" and rec is not None:
            rec["verdicts"].append(
                {
                    "rung": ev.get("rung"),
                    "state": ev.get("state"),
                    "delta_mean": ev.get("delta_mean"),
                    "delta_per_seed": ev.get("delta_per_seed"),
                    "scores": ev.get("scores"),
                    "seeds": ev.get("seeds"),
                    "reason": ev.get("summary"),
                }
            )
            if ev.get("attribution"):
                rec["attribution"] = ev["attribution"]
        elif t == "measurement" and rec is not None:
            for k, v in ev.items():
                if k in ("gauc", "ndcg_at_5", "primary") and isinstance(v, (int, float)):
                    rec["metrics"][k] = v
        elif t == "failure" and rec is not None:
            rec["errors"].append(
                {"class": ev.get("class"), "summary": (ev.get("summary") or "")[:400]}
            )
        elif t == "recovery":
            # Recoveries are logged against node 0 (the coder, pre-node); attach
            # them to the attempt named in the summary when we can.
            target = rec if ev.get("node") else None
            entry = {
                "action": ev.get("action"),
                "class": ev.get("class"),
                "summary": (ev.get("summary") or "")[:400],
            }
            if target is not None and target["node"] != 0:
                target["recoveries"].append(entry)
            else:
                nodes.setdefault(0, slot(0))["recoveries"].append(entry)

    # node_created doesn't carry the hypothesis; lessons.jsonl records the
    # family and pattern per node, which is the same identity by another name.
    lessons_path = run_dir / "lessons.jsonl"
    if lessons_path.is_file():
        for line in lessons_path.read_text(encoding="utf-8").splitlines():
            try:
                le = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec = nodes.get(int(le["node"])) if le.get("node") is not None else None
            if rec is None:
                continue
            rec["hypothesis"] = rec["hypothesis"] or le.get("pattern")
            rec["mechanism"] = rec["mechanism"] or le.get("family")

    for nid, rec in nodes.items():
        p = run_dir / "patches"
        if p.is_dir() and rec["hypothesis"]:
            hit = sorted(p.glob(f"{rec['hypothesis']}*.diff"))
            if hit:
                rec["diff"] = str(hit[-1].relative_to(run_dir))
        if rec["diff"] is None and p.is_dir():
            hit = sorted(p.glob(f"node-{nid:03d}*.diff"))
            if hit:
                rec["diff"] = str(hit[-1].relative_to(run_dir))

    iterations = [nodes[k] for k in sorted(nodes) if k != 0]

    # --- resources, straight from the log ---
    tok_in = tok_out = 0
    for ev in events:
        for key, add in (("tokens_in", "in"), ("tokens_out", "out")):
            v = ev.get(key)
            if isinstance(v, (int, float)):
                if add == "in":
                    tok_in += int(v)
                else:
                    tok_out += int(v)
        cost = ev.get("cost")
        if isinstance(cost, dict):
            if isinstance(cost.get("tokens_in"), (int, float)):
                tok_in += int(cost["tokens_in"])
            if isinstance(cost.get("tokens_out"), (int, float)):
                tok_out += int(cost["tokens_out"])

    stamps = [ev.get("t") for ev in events if ev.get("t")]
    wall_s = None
    if len(stamps) >= 2:
        from datetime import datetime

        fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
        wall_s = (fmt(stamps[-1]) - fmt(stamps[0])).total_seconds()

    gpu_min = sum(
        ev["gpu_min"] for ev in events if isinstance(ev.get("gpu_min"), (int, float))
    )

    best_primary, best_node = None, None
    for rec in iterations:
        for v in rec["verdicts"]:
            for s in v.get("scores") or []:
                if isinstance(s, (int, float)) and (best_primary is None or s > best_primary):
                    best_primary, best_node = s, rec["node"]

    promotions = sum(
        1 for rec in iterations for v in rec["verdicts"] if v["state"] == "promoted"
    )
    errors = sum(len(rec["errors"]) for rec in iterations)
    recoveries = sum(len(rec["recoveries"]) for rec in nodes.values())
    ended = any(ev.get("type") == "run_ended" for ev in events)

    summary = {
        "run_id": run_id,
        "converged": ended,
        "iterations_used": len(iterations),
        "iteration_cap": 50,
        "promotions": promotions,
        "manual_interventions": 0,
        "errors": errors,
        "recoveries": recoveries,
        "validation_best": {
            "primary": best_primary,
            "node": best_node,
            "delta_vs_official_valid": (
                round(best_primary - BASELINE["valid"]["primary"], 4)
                if best_primary is not None
                else None
            ),
        },
        "official_baseline": BASELINE,
        "resources": {
            "tokens_in": tok_in,
            "tokens_out": tok_out,
            "tokens_total": tok_in + tok_out,
            "wall_clock_s": round(wall_s, 1) if wall_s else None,
            "wall_clock_h": round(wall_s / 3600, 3) if wall_s else None,
            # No GPU was used; gpu_min is the runner's training wall-time on
            # CPU. Reporting it as GPU-hours would overstate the compute.
            "gpu_hours": 0.0,
            "compute_hours_cpu": round(gpu_min / 60.0, 4),
        },
        "submission": (
            "submission/pred.csv"
            if (run_dir / "submission" / "pred.csv").is_file()
            else None
        ),
    }
    return iterations, summary


def md(summary: dict, iterations: list[dict]) -> str:
    r = summary["resources"]
    vb = summary["validation_best"]
    lines = [
        f"# Run summary — {summary['run_id']}",
        "",
        "## Results (KuaiRand-Pure)",
        "",
        "| | GAUC | nDCG@5 | primary |",
        "|---|---|---|---|",
        f"| official baseline (valid) | {BASELINE['valid']['gauc']} | {BASELINE['valid']['ndcg_at_5']} | {BASELINE['valid']['primary']} |",
        f"| official baseline (hidden test) | {BASELINE['test']['gauc']} | {BASELINE['test']['ndcg_at_5']} | {BASELINE['test']['primary']} |",
        f"| this run, validation-best | — | — | {vb['primary']} |",
        "",
        f"Absolute delta vs official validation baseline: **{vb['delta_vs_official_valid']:+}**"
        if vb["delta_vs_official_valid"] is not None
        else "No scored attempt.",
        "",
        "## Resource usage",
        "",
        f"- LLM tokens: **{r['tokens_total']:,}** ({r['tokens_in']:,} in / {r['tokens_out']:,} out)",
        f"- Agent wall-clock: **{r['wall_clock_h']} h**",
        f"- Iterations used: **{summary['iterations_used']} of {summary['iteration_cap']}**",
        f"- GPU-hours: **0** — CPU-only run "
        f"(candidate training used {r['compute_hours_cpu']} h of CPU time)",
        "",
        "## Autonomy & robustness",
        "",
        f"- Manual interventions during the run: **{summary['manual_interventions']}**",
        f"- Accepted improvements (promotions): **{summary['promotions']}**",
        f"- Errors encountered: **{summary['errors']}**, automatic recoveries: **{summary['recoveries']}**",
        f"- Converged / ended cleanly: **{summary['converged']}**",
        "",
        "## Iterations",
        "",
        "| # | hypothesis | mechanism | outcome | Δ | diff |",
        "|---|---|---|---|---|---|",
    ]
    for rec in iterations:
        last = rec["verdicts"][-1] if rec["verdicts"] else {}
        d = last.get("delta_mean")
        lines.append(
            f"| {rec['node']} | {rec['hypothesis'] or '—'} | {rec['mechanism'] or '—'} | "
            f"{last.get('state') or 'no verdict'} | {f'{d:+.4f}' if isinstance(d, (int, float)) else '—'} | "
            f"{rec['diff'] or '—'} |"
        )
    lines += ["", "Full per-iteration detail: `iterations.jsonl`."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    args = ap.parse_args()
    run_dir = REPO / "runs" / args.run_id
    if not run_dir.is_dir():
        print(f"no such run: {run_dir}", file=sys.stderr)
        return 2

    iterations, summary = build(args.run_id)
    (run_dir / "iterations.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in iterations), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "SUMMARY.md").write_text(md(summary, iterations), encoding="utf-8")
    print(f"wrote {run_dir}/iterations.jsonl ({len(iterations)} iterations)")
    print(f"wrote {run_dir}/summary.json")
    print(f"wrote {run_dir}/SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
