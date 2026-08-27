# Plan delta · 27 Aug — execute-first addendum

Planning stops here. Backend_plan.md stands; the four decisions below are the only
additions, chosen because they are the ones that get expensive to change later.
Everything else gets decided inside the PR that needs it. Build_steps.md gets a
Phase-N page (in the Phase-1 format) only when that phase starts — never further
ahead than one phase.

## 1 · The event schema grows without breaking the app

Already true in code — promoted to a rule so future types stay cheap:

- **Adding** a new event type, or a new optional field to an existing type, is
  NOT a schema bump. The reducer ignores unknown types (it already does) and
  unknown fields. Any new type displays generically for free because every line
  carries the six stamps plus `summary`; a dedicated view can come later or never.
- **Renaming or removing** a type or field, or changing the meaning of an
  existing one, IS a bump: `schema_version + 1`, reducer updated in the same PR.
- `fake_run.py` is the schema's living test: every type in `EVENT_TYPES` appears
  in its script, so the app is exercised against the full vocabulary before the
  real backend ever emits it. A PR that adds a type extends the fake run script
  in the same PR.

## 2 · Ranking is arithmetic over the log

The `Hypothesis` dataclass in `types.py` (already frozen) is the only currency:
the step-6 hand-written list, the step-7 researcher, and the tuner's shortlist
all emit it, and ranking code never knows which source produced one.

- Queue priority = family-level evidence folded from `verdict` events:
  `(mean Δ + 1 SD) / mean gpu-min` per family. A hypothesis's own
  `expected_gain` is a cold-start prior and tie-break only. The LLM never
  writes a priority — evidence updates are arithmetic on our own log
  (Gupta 2025: LLM agents don't update on experimental feedback; bandit
  arithmetic does).
- Tuner: ask-and-tell, screen rung only, each trial a `trial`-kind child node so
  the cost slice and trial table fall out of the log with nothing extra built.
  Under ~10 trials there is no study — enqueue 2–3 hand-picked configs.
- Search policy stays greedy + fork-on-stall per §7. No bandit, no MCTS.

## 3 · Crash recovery = replay

Design rule adopted now, implemented in step 6, nothing built before then:

- `tree.py` may hold no state that is not a fold over `events.jsonl` — the same
  rule the frontend already lives by. If the loop needs to remember it, it must
  have been emitted.
- `python -m harness resume <run-id>`: replay the log, rebuild nodes / queue /
  incumbent; any node `running` with no verdict gets
  `failure(class="orphaned")` and is requeued as a new attempt (attempt counter
  increments; nothing is edited retroactively); then the loop continues.
- The runner's child writes `result.json` atomically (tmp file + rename) so a
  half-written result reads as absent, never as corrupt.

## 4 · Minimal-first ladder — what we cut to move fast

Step 5 ships only: rung-0 band, reject-only screen, k=3 replicate promoting to
"promising". That is enough to drive the loop and the demo. Deferred until after
the first real Ali-CCP run: BH correction, the holdout/DiD confirm rung,
checkpoint sensitivity, the description test. All are additive to `measure.py`
and the event schema already carries their fields. The holdout *split* itself
still lands with step 8 and stays capability-protected (never mounted for the
candidate) even while the confirm rung is deferred.

## Execution order from here

3 (synthetic + template) → 4 (runner) → 5-minimal → 6 (tree + resume) →
7 (agents) → 8 (ingest + aliccp) → 9 (outputs + audit) → 10 (rulebook).
The fallback demo stays step 6. Break-and-fix beats spec-and-stall from here on:
the log is the contract, so anything behind it can be rewritten cheaply.
