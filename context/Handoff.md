# Handoff — execution agent instructions · 27 Aug

You are picking up a hackathon harness ("beating NISE") whose planning is
finished and whose first two build steps are merged. Your job is to execute
build steps 3–10. Do not iterate the plan; decisions go in the PR that needs
them.

## Read these, in this order

1. `context/Plan_delta.md` — the frozen decisions (schema evolution, ranking,
   crash recovery, minimal ladder, NOVA/AgentX search-loop + retry layer) and
   the execution order. This overrides anything that conflicts with it.
2. `context/Backend_plan.md` — the full spec. §A has the file map, build order,
   and per-step scope; read the section for the step you are on (§10 for the
   synthetic task, §5 for the runner, §6 for measurement, §7 for the tree,
   §8 for agents).
3. `context/Build_steps.md` — Phase 1 is the format template: goal, in/out of
   scope, interfaces, locked decisions, named tests, gate, hands-forward.

## Current state

- Merged to main: phase 0 (skeleton, `harness/types.py`), phase 1
  (`protocol.py`, `events.py`, `python -m harness init`), phase 2
  (`fake_run.py`, `app/server.py` SSE, reducer + three views).
- Everything else under `harness/` is a stub that raises `NotImplementedError`,
  guarded by `tests/test_00_skeleton.py` (`test_stubs_raise` with an
  `IMPLEMENTED` set you extend in each phase's PR).
- Tests: `pytest` from the repo root; reducer tests are
  `app/static/reducer.test.js` (node). Smoke: `python -m harness init
  protocols/synthetic.yaml` then `tail runs/<id>/events.jsonl`.

## What to build, in order

| Step | Scope | Delta sections that bind it |
|---|---|---|
| 3 | `tasks/synthetic.py` (planted effects per Backend_plan §10), `candidate/template.py` + `candidate/report.py` | write the candidate-contract rules here (§5) |
| 4 | `runner.py`: spawn, derived timeout, heartbeat | typed retry table, failure classifier, watchdog, never-wedge invariants (§6) |
| 5 | `measure.py` minimal: rung-0 band, reject-only screen, k=3 replicate | deferred items listed in §4 — do NOT build BH/DiD/holdout yet |
| 6 | `tree.py` with a hand-written hypothesis list + `harness resume` | ranking is arithmetic over the log (§2); replay-based resume (§3). This is the fallback demo |
| 7 | `agents/`: researcher, coder, tuner, brief, cache | semantic pre-run check, K=2–3 candidates at expensive rungs, rules.jsonl accumulation (§5); llm_api retry + degraded mode (§6) |
| 8 | `data/ingest.py` + `tasks/aliccp.py` | holdout split capability-protected (never mounted for the candidate) |
| 9 | `outputs.py` + `audit.py` | projections only; always-valid-submission invariant (§6) |
| 10 | leak-audit post-checks, thresholds from the first real run | optional: falsifiable attribution (§5 tail note) |

Steps must each be runnable on the synthetic task alone. Do not touch real
Ali-CCP data before step 8.

## Working rules

- **Per step**: write the Phase-N page in `Build_steps.md` (Phase-1 format,
  one page, tests named) as part of the same PR — never further ahead than the
  step you are starting.
- **Branching**: branch `phase-N-<slug>` off main, commit when green, open a PR
  to main. Phases 1–2 were merged via PR; follow that.
- **The event log is the only seam.** Every module reports via `EventLog.emit`
  and never reads another module's state. Adding event types or optional fields
  is free (the reducer ignores unknowns — keep it that way); renaming/removing
  anything bumps `schema_version` and updates the reducer in the same PR. Every
  new event type must also appear in `fake_run.py`'s script in the same PR.
- **`types.py` changes are exceptional** — it is the two-person seam; change it
  only when a step's spec requires it and say so in the PR description.
- **LLMs judge nothing numerical.** Metrics come from `result.json` parsed
  deterministically; verdicts from `measure.py` arithmetic; queue priorities
  from folds over verdict events. No LLM-produced number enters a decision.
- **Watch your work in the app**: run `app/server.py`, point the browser at it,
  and use `fake_run.py` / real runs to verify events render. If a backend step
  emits something the app can't show, file it, don't silently extend the schema.

## Gotchas

- `protocols/aliccp.yaml` has seven nulls awaiting the organisers' webinar
  (28 Aug). Paste values in when known; a tightened rule means a new versioned
  yaml (append-only), never an edit that changes an existing run's hash.
- The synthetic task's planted +0.01 effect must be sized above the certifiable
  threshold *for the synthetic's own σ* (see critique history: a +0.01 effect
  at Ali-CCP noise passes a one-seed screen only ~37% of the time — make the
  synthetic quiet or the self-test flakes).
- "Failed" is not a node state. It is a `failure` event on a node that is
  `debugging`; states are the nine words in `types.py` and nothing else.
- Retries are new attempt events with counted cost; nothing is edited
  retroactively.
- Develop and test on CPU throughout; `run.device` in the protocol's run block
  (not hashed) selects the device.
