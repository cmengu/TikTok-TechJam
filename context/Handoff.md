# Handoff — Phase 6 (run tree · hand-written hypotheses) · 27 Aug

You are picking up after Phase 5. Planning is frozen; do not re-open it.
Decisions that are still open go in the Phase-6 PR description, not in a new
plan doc. **Locks 1–4 are confirmed (27 Aug) — see §Locked decisions below.
Do not re-open them.**

## Read these, in this order

1. This file.
2. `context/Plan_delta.md` — §2 ranking arithmetic (queue score from verdict
   events; LLM never writes priority); §3 crash recovery = replay (`tree.py`
   holds no state that is not a fold over `events.jsonl`; `resume` called out
   for step 6 — confirm vs Build_phases before coding).
3. `context/Backend_plan.md` §7 — greedy + fork-on-stall, lessons file, at most
   three live branches (older prose; where it fights `#p6`, `#p6` wins once
   locked).
4. `context/Build_phases.html` §Phase 6 (`#p6`) — **interfaces, constants,
   named tests, gate.** Detailed build page until you write the Phase-6 page
   into `Build_steps.md`.
5. `context/Build_steps.md` — Phase 1 is the page format; Phase 5 is already
   there. Write the **Phase 6** page in that format in the same PR; never write
   Phase 7+ ahead.
6. Skim `context/Build_steps.md` Phase 5 + `harness/measure.py` — Phase 6
   **calls** `Measure.verdict` / `holdout_report` / `calibrate_from_runs`; it
   does not reimplement the ladder.

## Current state (merged to main)

Confirm with `git log origin/main --oneline -8`. As of this handoff:

- **Phases 0–5 on main**, including:
  - Phase 5 / PR #10 (`phase-5-measure`): Redline measurement — `Band`,
    screen/replicate verdicts, leak + attribution gate, `holdout_report` (≤2),
    ρ refresh; pure tests + slow 200K scorecard
    (`FP=0 FN=0 marginal=inconclusive leak=caught`).
  - Event types already include `incumbent_changed` and `prediction`.
  - Phase 3–4: four planted effects, capability-safe `candidate/`, runner,
    `run-one` CLI, app event-log / follow-newest-run.
- **Open / not required for Phase 6:** `fix/phase-2-review` (SSE partial-line,
  runs-path, fake-wipe, lastSeq) — independent; do not block on it.

### What you inherit

| Area | Location | Notes |
|---|---|---|
| Measure | `harness/measure.py` | Authority for node state after screen/replicate. `SeedCache`, `holdout_report` ≤2, no smoke logic (`RungMismatch` on smoke). Pass `attribution=` in (phase 7 will adjudicate; hand loop may pass `"clear"`). |
| Runner | `harness/runner.py` | Only training path. Smoke = short contract run (no score judgement in measure). |
| Synthetic + candidate | `harness/tasks/synthetic.py`, `candidate/*` | Planted `f_true` / `f_marginal` / `f_zero` / `f_leak`. Template reads `FEATURES`. Patches in phase 6 are one-line `FEATURES` default changes. |
| Events | `harness/events.py`, `harness/types.py` | Vocab locked; additive types OK (Plan_delta §1). No state `"failed"`. |
| Stub | `harness/tree.py` | Skeleton with empty `TRANSITIONS`, `PatchCoder` / `Workspace` / `Queue` / `Tree` raising. **Fill to match `#p6`.** |
| CLI | `harness/__main__.py` | Has `init` / `run-one`; add `run` (and `resume` only if lock says yes). |
| Tests | `pytest` from repo root (`.venv`) | Default skips `slow`. Phase-5 scorecard: `pytest tests/test_05_scorecard.py -m slow`. |

App watch: `python -m app.server` / `python -m harness.fake_run` /
`python -m harness run-one …`. After Phase 6: `python -m harness run
protocols/synthetic.yaml --hypotheses hypotheses/hand.yaml`.

## What to build now — Phase 6 only

| File | Role |
|---|---|
| `harness/tree.py` | `TRANSITIONS`, `PatchCoder`, `Workspace`, `Queue`, `family_stats`, `Tree.step` / `Tree.run` |
| `harness/__main__.py` | `run` command (wire protocol → events → calibrate → queue → tree) |
| `hypotheses/hand.yaml` | Five hand hypotheses: base, +f_true, +f_marginal, +f_zero, +f_leak |
| `hypotheses/patches/*.diff` | One-line `FEATURES` default patches for those five |
| `tests/test_06_tree.py` | Named unit tests — fake runner + fake measure, real `EventLog` |
| `tests/test_06_loop.py` | `@pytest.mark.slow` — real runner + real measure, ~200K, four planted hyps |
| `context/Build_steps.md` | Phase-6 page (Phase-1 format) |

Extend `IMPLEMENTED` with `"harness.tree"` in this PR.

**Out of scope:** any LLM call; Optuna / tuner (phase 7); convergence ε/N stop
(phase 9 — here stop on empty queue, `max_nodes`, or budget); MCTS / UCT /
bandit / island / ensemble; rewriting measure constants or planted AUC bands;
Ali-CCP ingest (phase 8); inventing attribution labels (pass through
`attribution=`; hand demo may use `"clear"`).

### Interfaces (from Build_phases `#p6` — implement these)

```python
TRANSITIONS = {  # only legal edges; else IllegalTransition
  "screening": {"running", "retired"},
  "running": {"replicating", "inconclusive", "rejected", "debugging", "leaked", "retired"},
  "replicating": {"promoted", "inconclusive", "rejected", "leaked", "retired"},
  "debugging": {"running", "retired"},
  "inconclusive": {"replicating", "retired"},
  "promoted": {"retired"},
  "rejected": set(), "leaked": set(), "retired": set(),
}
STALL_STEPS = 4
MAX_LIVE_BRANCHES = 3
DEBUG_DEPTH = 3
LESSONS_WINDOW = 30

class Coder(Protocol):
    def materialise(self, hyp: Hypothesis, incumbent: Node, traceback: str | None) -> Path

class PatchCoder:  # phase 6: copies hyp.patch; ignores traceback

class Workspace:   # git repo at runs/<id>/workspace; branch run/<id>; initial commit = template
    def commit_node(self, node_id, diff_path) -> str   # apply + commit "node NNN"; write patches/node-NNN.diff
    def checkout(self, commit) -> None

class Queue:
    def push(self, hyp) -> bool          # False + rule_trip "duplicate" if key(stage, mechanism, norm(description)) seen
    def rerank(self, family_stats) -> list[str]  # (mean Δ + 1·sd) / mean gpu_min; emits queue_reordered
    def pop(self) -> Hypothesis

def family_stats(events: list[dict]) -> dict[str, dict]  # pure over verdict events

class Tree:
    def __init__(self, events, protocol, task, runner, measure, coder, queue, max_nodes, budget): ...
    def step(self) -> bool   # one dequeue → node → ladder → verdict → update; False when done
    def run(self) -> None    # while step(): pass; emit run_ended with incumbent + counts

# CLI: python -m harness run protocols/synthetic.yaml --hypotheses hypotheses/hand.yaml [--max-nodes N]
```

**Ladder per node (driven by Measure, not reimplemented):**  
smoke (60 s contract) → screen (1 paired seed) → if `replicating`: 3 full-rung
runs → `measure.verdict(rung="replicate")`. **No holdout inside the ladder.**  
Holdout: `measure.holdout_report()` **exactly twice per run** — first promotion
and run end. Greedy: incumbent only on `promoted`; else checkout incumbent
commit. Stall: `STALL_STEPS` non-promoted improve nodes → fork two drafts into
the two best *other* families; ≤ `MAX_LIVE_BRANCHES` in running/replicating.
Debug: crash/contract_violation and depth < 3 → debugging + coder with
traceback. Lessons: after every full-rung run append one line to
`runs/<id>/lessons.jsonl`.

### Named tests

**Unit — `tests/test_06_tree.py`** (fake runner + fake measure, real EventLog):  
`test_illegal_transition_raises`, `test_queue_order_by_score`,
`test_rerank_after_rejection`, `test_dedupe`, `test_ladder_progression`,
`test_seed_cache_rolls_on_promotion`, `test_holdout_twice_per_run`,
`test_greedy_revert`, `test_fork_on_stall`, `test_max_live_branches`,
`test_debug_depth`, `test_git_per_node`, `test_lessons_appended`,
`test_loop_emits_only_vocab`.

**Slow — `tests/test_06_loop.py`** (real runner + real measure, ~200K, hand hyps):  
`test_incumbent_is_f_true` — at `run_ended`, incumbent hyp is `+f_true`;
`+f_leak` is `leaked`; `+f_zero` not promoted; `+f_marginal` not rejected.  
`test_holdout_visits_le_two` — ≤2 `measurement(rung="holdout")`.  
`test_run_completes_unattended` — no `intervention`; `run_ended` present.

### Gate

All tests green. Manual fallback demo:

```bash
python -m harness run protocols/synthetic.yaml --hypotheses hypotheses/hand.yaml
```

with the app open: tree grows, fork-on-stall visible if it triggers, incumbent
changes to `+f_true`. **Record that run id** — demo of last resort for judges.
If the slow loop fails on planted outcomes: retune phase-3 **weights** or fix
tree wiring — **never loosen Redline measure constants**.

## Locked decisions (Phase 6 · 27 Aug)

1. **Seeds: 1,2,3 everywhere.** Not 0,1,2. Phase 5's `calibrate_from_runs`,
   SeedCache keys, and the merged scorecard all use 1,2,3; changing to 0,1,2
   buys nothing and would touch `measure.py`. Screen paired seed = **1**
   (`fixed_pair` default). Note in the PR that `#p6`'s "0,1,2" is stale.
2. **`resume` CLI: defer.** Build `Tree.rebuild(events)` — a pure fold that
   reconstructs nodes/queue/incumbent from `events.jsonl` — plus named test
   `test_rebuild_matches_live`. No `resume` verb in this PR; say so in the PR
   description.
3. **`orphaned`: moot** given #2. Do not add `"orphaned"`, do not map it to
   `crash`. Leave the class decision for the follow-up that adds `resume`.
4. **`attribution="clear"`** for all hand hypotheses.

**Extra (same PR):** `incumbent_changed` case in `app/static/reducer.js`
(`state.incumbent`) and render it in `app.js`. Commit this handoff in the PR.

### Code facts (why seeds stay 1,2,3)

`Measure.calibrate_from_runs` defaults `full_seeds` to `[1,2,3]`.
`SeedCache.get` raises `MissingIncumbentSeed` for any seed not in the cache.
Plan_delta §3's `orphaned` is not in `runner.FAILURE_CLASSES` — deferred with
resume.

Also honour locks from prior phases:

- Metrics only from `task.score` / `RunResult.metrics` — never child self-report.
- Capability: never mount holdout / `harness_only` / `protocols/` on the child;
  candidate stays under repo `candidate/`, copied into workspace.
- `tree.py` state = fold over the event log (Plan_delta §3); no silent side
  memory that a future resume cannot rebuild. `Tree.rebuild` is the fold.
- Queue score = family arithmetic over verdicts (Plan_delta §2); `expected_gain`
  is cold-start / tie-break only.
- Failure class names stay runner vocabulary; measure does not reclassify them.

## Working rules

- Branch `phase-6-tree` off **updated main** (PR #10 already merged), green → PR.
  Never stack on an unmerged fix branch.
- Event log is the only seam; emit only vocab types/states; no `"failed"`.
- Fake runner + fake measure for `test_06_tree.py`; real stack only in
  `@pytest.mark.slow` `test_06_loop.py`.
- CPU only; synthetic task only. Five hand patches — no LLM coder yet
  (`PatchCoder` copies `hyp.patch`).
- Scorecard-style loop will be slow (~minutes); keep default pytest skipping
  `slow`.
- Extend `fake_run.py` only if a new event type is added (Plan_delta §1).

## What NOT to do

- Do not start Phase-7 agents / Optuna / `bank.yaml` researcher.
- Do not reintroduce BH, bootstrap, Student-t, or DiD into measure.
- Do not loosen Redline constants or widen planted AUC test bands to green the
  loop.
- Do not put holdout in `candidate_env` or teach the child to score.
- Do not implement MCTS, UCT, ε-greedy exploration, or ensembling.
- Do not “helpfully” have an LLM write priorities or expected gains that bypass
  `family_stats`.

## Hands forward after Phase 6

Phase 7 swaps `PatchCoder` for `LLMCoder` and fills the queue from a researcher
instead of `hand.yaml`. **Nothing else in the loop should need to change** — the
`Coder` seam and `Queue` are the swap points. Phase 9 later adds convergence ε/N
stop; until then empty queue / `max_nodes` / budget end the run.
