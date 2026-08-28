# Handoff — Phase 9 (outputs and audit), built BEFORE phase 8 · 28 Aug

Planning is frozen. **Read this page first.** Open questions go in the PR
description, never in a new plan doc.

## The reordering decision (read this before anything else)

`Build_phases.html` `#p9` says "Depends on phases 6, 8". **We are building phase 9
before phase 8, deliberately.** The dependency is about usefulness, not
buildability:

- `tests/test_09_audit.py` runs against the **fake run stream** (`harness/fake_run.py`),
  which already exists and already contains every event type.
- The `#p9` gate is "the Audit tab shows real numbers on the phase-6 fallback run
  and on a synthetic run with agents" — synthetic, not Ali-CCP.
- `test_convergence_rule` supplies its own ε=0.001 and N=3, so the mechanism is
  testable without the organisers' real values.

Only two things in phase 9 need the organisers, and **both are config, not code**:

1. `write_submission(mode="predictions")` — the exact column list, from the
   organisers' example submission file.
2. The real ε / `n_rounds` in `protocols/aliccp.yaml` (`convergence:` block).

Build both with those values as **parameters**. Leave `aliccp.yaml`'s convergence
block `null`. Put test values in the synthetic protocol. Do not guess the real
ones.

**Why this order helps.** Iteration 0 in phase 8 is five full baseline runs on
booked GPU time. Running that without cost tracking, reliability, or replication
pairs means a failure at hour three is invisible until it is expensive. Build the
instrumentation before the run that needs it. It also removes MLE-bench's top
failure mode (Plan_delta §6: "never produced a valid submission") from the
deadline crunch.

## Read these, in this order

1. This file.
2. `context/Build_phases.html` `#p9` — **the primary spec**: interfaces, the 13
   named tests, the gate. Transcribed below, but read the source.
3. `context/Plan_delta.md` §1 (event schema growth rule) — phase 9 must add **no
   new event type**, and §1 tells you why that rule exists.
4. `context/Build_phases.html` "Rules for every phase" — especially *"Touch only
   the files listed under In scope. If the work seems to need a change elsewhere,
   stop and report the need; do not make the change."* Phase 7 broke this rule and
   it cost a day of untangling. Do not repeat it.
5. Skim `harness/fake_run.py` (your test fixture), `harness/measure.py`
   `holdout_report` (already emits `prediction` — see Trap 1), and `app/server.py`
   (four routes today; you add three).

## Current state · confirm before you start

    git status -sb && git log --oneline -3

As of this handoff:

- **`main`** — phases 0–6.
- **`phase-7-agents` @ `56532ba`** — agents work, local, no PR. `tree.py` diff is
  only ~21 lines (in scope).
- **`fix/phase-6-review` @ `4810701`** — the phase-6 ladder rewrite (434 lines of
  `tree.py`), runner rungs, `measure.py` constants, `events.drain()`. Not merged.
- **Untracked:** `context/organisers_brief.md`, `scripts/` (one-shot codemods —
  delete them, they are already applied and are non-idempotent).
- **A Cursor agent has been committing in this repo.** Re-run `git log` before you
  trust any of the above.

### Blockers — clear these first, in this order

1. **`pip install -e .`** — `optuna` is not installed, so pytest **aborts during
   collection** and the *entire* suite is unrunnable, not just the tuner file.
   `pyarrow` is also 23.0.1 against a pinned 25.0.1. You cannot claim a green
   suite until this is done.
2. **Land the branch mess.** Phase 9 edits `tree.py`, and there are currently two
   competing versions of that file. Merge `fix/phase-6-review`, then rebase
   `phase-7-agents` onto it. **When you rebase, re-apply the `refill_queue` call
   in `Tree.step()`** — `4810701` rewrote `step()` and dropped it, so the agent
   path dies silently. Add a test asserting it fires on an empty queue.
3. **Fix the four open phase-7 defects** (all verified at `56532ba`):
   - `HOLDOUT_SEEDS` is defined twice: `measure.py:35` = `3` (int, correct per
     spec — `test_holdout_candidate_side_only` needs "exactly HOLDOUT_SEEDS runs")
     and `tree.py:49` = `(0, 1, 2)` (tuple). The seeds lock says **1,2,3**, and
     `calibrate_baseline`'s own docstring says "seeds 1,2,3 (locked)". So the
     holdout path runs candidates on 0,1,2 against an incumbent cache keyed on
     1,2,3 → `MissingIncumbentSeed` on the first holdout visit. Rename the tree
     constant (e.g. `HOLDOUT_RUN_SEEDS = (1, 2, 3)`); do **not** retype the
     phase-5 constant.
   - `check_prompt_capability` is never called on the researcher prompt
     (`researcher.py`) — the brief leaks freely. Coder-only today.
   - `brief.py:12` cuts on `"## 0 · The one principle"`, which does not appear in
     `context/organisers_brief.md`. Switch to the `<!-- brief-end -->` marker that
     brief already carries.
   - `cache.put` is never called anywhere, so the `confirmed|contradicted` label
     that `test_cache_hit_same_hash_miss_other_hash` requires can never be
     produced.

## Phase 9 · Outputs and audit — the whole spec

**Owner** A: submission writer · B: audit, report, registry
**Source** `#p9` / Backend_plan §9

### Goal

Pure projections over a log that already exists (replication, cost, reliability),
the submission writer with its read-back check, the organisers' convergence rule,
the pre-scoring prediction with its band, the run registry, and the report. The
Audit tab lights up.

### In scope — touch nothing else

`harness/audit.py`, `harness/outputs.py`, `app/server.py` (**three audit endpoints
only**), `harness/tree.py` (**exactly two calls**: convergence check per verdict,
submission on promotion — *nothing else*), `reference/published_costs.yaml` (AIDE
and MLE-bench figures **with sources**), `tests/test_09_audit.py`,
`tests/test_09_outputs.py`, and this page's successor in `Build_steps.md`
(Phase-1 format, written in the same PR).

### Out of scope

Any new event type. Pooling runs with different protocol hashes (must refuse).
Frontend rendering of the Audit tab beyond wiring the three endpoints. Phase 8
(Ali-CCP). Phase 10 (`POS_TOL` needs an observed real run).

### Interfaces

```python
# audit.py — every function takes list[dict] events, returns plain dicts; NO I/O
def replication_pairs(events) -> list[{node, screen_vs_full, one_vs_many_seeds,
                                       searchval_vs_holdout}]
def cost_by_slice(events) -> {researching|coding|training|tuning:
                              {tokens_in, tokens_out, gpu_h}}
    # gpu_h = allocated wall time x device count, NOT utilisation
def reliability(events) -> {failures_by_class, recoveries: {ok, failed},
                            time_to_first_valid_submission_s,
                            longest_unattended_s,   # max gap between intervention
                                                    # events, or the run length
                            rule_trips}
def assert_single_protocol(events) -> None      # raises if >1 distinct protocol_hash

# outputs.py
def write_submission(node, task, protocol,
                     mode: Literal["predictions","checkpoint"], out_dir) -> Path
    # predictions: columns from the example submission (PARAMETER — see the
    #   reordering note); head = p_conversion_given_click (refuse otherwise);
    #   read-back: row count == task.rows("test"), all columns present,
    #   values in [0,1], no NaN
    # checkpoint: copy checkpoint + inference script; dry-run inference on
    #   search-val must reproduce the node's cvr_auc +/- 1e-4
    # emits submission_written with path and read-back result
class Convergence:
    def __init__(self, eps, n_rounds): ...      # organisers' rule verbatim
    def update(self, searchval_score) -> bool
def write_prediction(events, holdout_score, band) -> int
    # a measurement event {kind: "prediction", delta, band}; MUST precede scoring
def register(run_dir, protocol, status, final_scores) -> None   # runs/index.jsonl
def report(events, out_path) -> Path
    # markdown: scorecard (FP, FN-strong, marginal rate, leak, recovery),
    # tree summary, costs, reliability

# server.py additions (three, no more)
GET /runs/{id}/audit/replication
GET /runs/{id}/audit/cost
GET /runs/{id}/audit/reliability
```

### Tests to pass — `tests/test_09_audit.py` (fake run stream; counts are fixed)

`test_cost_slices_sum` — the four slices' token totals equal the sum of cost
fields in the stream.
`test_reliability_counts` — failures by class and recovery outcomes equal the
scripted counts; `rule_trips` equals the number of `rule_trip` events.
`test_longest_unattended` — with one `intervention` at a known seq, the gap is
computed on both sides and the max returned.
`test_replication_pairs_per_node` — nodes that reached holdout have all three
pairs; screen-only nodes have one.
`test_refuse_mixed_hashes` — two streams with different hashes concatenated →
raises.
`test_endpoints` — the three endpoints return the same dicts as the functions.

### Tests to pass — `tests/test_09_outputs.py`

`test_wrong_head_refused`.
`test_readback_catches_row_count_and_range` — a short file and a file with 1.2 in
it both raise **before** `submission_written`.
`test_checkpoint_dry_run` — the copied checkpoint reproduces the node's search-val
score.
`test_convergence_rule` — for ε=0.001, N=3 and a scripted score sequence, `update`
returns True at exactly the expected index.
`test_prediction_precedes_submission` — the prediction event's seq is lower than
`submission_written`'s.
`test_registry_line` — one JSON line with run id, task, hash, status, scores.
`test_report_renders` — from the fake run, without error, containing the five
scorecard headings.

### Gate to phase 8

All tests green (whole `tests/` directory, every earlier phase included). Manual:
the Audit tab shows real numbers on the phase-6 fallback run and on a synthetic
run with agents. A submission file is written on the first promotion and passes
read-back.

## Traps specific to phase 9

1. **`prediction` is already emitted.** `measure.py:508` emits it from
   `holdout_report` when `ladder_accepts` passes, and `fix/phase-6-review`'s
   `tree.py` emits it too. `outputs.write_prediction` is a third site. **Reconcile
   before you write it** — decide on one emitter (measure is the natural owner,
   since it holds the band) and make `write_prediction` either delegate or be
   deleted. Do not add a fourth.
2. **`EVENT_TYPES` is 18, not the spec's 16.** `incumbent_changed` and
   `prediction` were added legitimately under Plan_delta §1 (additive types are
   not a schema bump, and `fake_run.py` was extended in the same PR, as the rule
   requires). Phase 9 adds **none**. If you think you need one, stop and report.
3. **`tree.py` gets exactly two calls.** Convergence check per verdict, submission
   on promotion. Phase 7 treated a similar limit as advisory and produced a
   434-line rewrite that had to be surgically extracted. Hold this line.
4. **`assert_single_protocol` must refuse, not warn.** Pooling runs across
   protocol hashes is the one thing that would silently invalidate every number in
   the report.
5. **`gpu_h` is allocated wall time × device count**, not utilisation. A judge will
   ask, and the honest number is the bigger one.
6. **`reference/published_costs.yaml` needs real sources.** It is currently `[]`
   with a comment. AIDE and MLE-bench figures, each with a citation — this is
   judge-facing material, so no unsourced numbers.
7. Do not implement `harness resume` or `"orphaned"` (still deferred).

## Carried locks (do not re-open)

| Topic | Decision |
|---|---|
| Seeds | **1,2,3** everywhere (screen paired seed **1**). `#p6`'s 0,1,2 is stale. |
| Event seam | The log is the only seam. Additive types OK per Plan_delta §1; phase 9 adds none. |
| Queue priority | `family_stats` arithmetic only; the LLM never writes priority. |
| Capability | Coder **and researcher** prompts never see holdout, `protocols/`, `measure.py`, rulebook. |
| Holdout | Never mounted in the child env. Harness-only. Max 2 visits per run. |
| Numbers | No invented thresholds. Every constant carries a rule reference. |
| Precedence | **Unresolved — decide in this PR.** `#p7` and Plan_delta §5 disagree about what lands when; that conflict caused phase 7's drift. Write one line saying which document wins and put it at the top of `Plan_delta.md`. |

## Working rules

- Never stack PRs. Merge `fix/phase-6-review` → rebase `phase-7-agents` → merge →
  branch `phase-9-outputs` off updated `main`.
- `pip install -e .` before any claim that tests pass.
- Tests run offline, CPU, no LLM, no GPU, under 60 s except `slow`.
- Regression is part of the gate: the whole `tests/` directory, not just phase 9.
- Write the Phase-9 page into `Build_steps.md` in this PR. Never write phase 10
  ahead.

## What NOT to do

- Do not start phase 8 (Ali-CCP). It is blocked on the organisers' webinar for
  seven `pending` values in `aliccp.yaml`, and the raw files are not downloaded.
- Do not guess the organisers' submission columns or convergence ε/N.
- Do not re-apply `scripts/patch_phase6_*.py` or `scripts/apply_phase7_*.py`.
- Do not touch `measure.py` constants, `types.py`, or the ladder.
- Do not build the Plan_delta §5/§6 research-paper items (K-candidates, LLM diff
  review, rules accumulation, structured lessons). They are deferred to a
  session-3 addendum because they need real runs to tune against. **Exception:**
  degraded mode (`llm_api` backoff → rotate model → fall back to the hand-written
  bank) is cheap demo insurance and may land with phase 7 if time allows.

## Hands forward

Phase 8 (Ali-CCP) once the webinar lands, with the Audit tab already watching
iteration 0. Then phase 10, whose `POS_TOL` can only be set from an observed real
run.
