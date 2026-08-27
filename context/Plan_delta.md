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

## 5 · Search-loop architecture, aligned with NOVA / AgentX
*(NOVA, arXiv:2606.27243; AgentX, arXiv:2606.26859 — the two production systems
closest to this harness. What transfers is listed here; what doesn't is at the end.)*

- **Verify before you spend a run** (NOVA's verification cascade; their ablation:
  removing it costs −30 EPR points). Between coder and runner sits a semantic
  check of the diff — cheap, no training. It enforces the candidate contract:
  trains only on the TRAIN path, evaluates the declared population on full
  search-val, writes the declared head (`p_conversion_given_click`, not the
  product), honors SEED/DEVICE, calls `report.progress` and checkpoints, no
  label-derived feature uses the row's own label. Mechanics: static greps plus
  one LLM review of the diff against the active rule list. Fail → back to the
  coder (counts against debug depth ≤ 3), never into the runner. Lands with
  step 7; the contract rules themselves are written at step 3 with the template.
- **Rules accumulate from confirmed errors** (NOVA's forbidden patterns → rules).
  When a failure or an implausible result is root-caused, the diagnosis is
  appended as a new semantic-check rule in `runs/<id>/rules.jsonl` and applied to
  every later candidate; the discovery emits `rule_trip`. Same mechanism feeds
  the family-level "forbidden directions" the §2 ranking already demotes.
- **K candidates per expensive run** (NOVA generates K=4, evaluates 1; ranking
  removal cost them −40 EPR points). Generation is tokens, evaluation is
  GPU-hours — so at the full/replicate rung the coder produces K=2–3 diffs and
  the semantic check + a short LLM rank picks one. At the screen rung K=1: a
  screen is cheap enough to just run.
- **LLMs judge nothing numerical** (AgentX: "an LLM is permitted to be wrong only
  on judgment; every objective fact is produced by deterministic code"). Metrics
  come from `result.json` parsed deterministically; verdicts from measure.py
  arithmetic; consensus/priority by code. This is §2's rule restated from their
  side — it survives contact with production, keep it absolute.
- **Trajectory feedback is structured, not prose** (NOVA's z = weak components /
  directions / forbidden). The lessons file the tree feeds back into the
  researcher prompt uses those three headings, synthesized from verdict events —
  not a free-text diary.

## 6 · Retry loops and edge cases — the autonomy layer
*(AgentX §5.2.3 verbatim where it fits; their production numbers justify the
investment: >90% of loop failures were infrastructure-side, not agent reasoning.)*

- **A pure-function failure classifier** in runner.py maps (exit code, stderr
  tail, result.json presence, self-reported progress) → one reason code.
  Deterministic-first priority order: NaN/contract/schema errors are checked
  before infra symptoms, so a transient-looking abort can't mask a real bug
  (AgentX evaluates `ps_aborted`-style codes last for exactly this reason).
- **Typed retry policy — the table, locked at step 4:**

  | class | signal | policy |
  |---|---|---|
  | `nan_loss` | report.progress NaN / loss > k× initial | abandon (deterministic — retrying cannot help); family note |
  | `oom_gpu` | "CUDA out of memory" in trace | retry once, batch halved |
  | `oom_host` | exit 137, no trace | retry once, loader workers halved |
  | `crash_code` | import/syntax/runtime traceback | to coder debug, depth ≤ 3 |
  | `no_result` | exit 0 but no/invalid result.json | to coder debug once, then abandon |
  | `stall` | no heartbeat/progress for max(5 min, 3× median step) | kill, retry once (transient) |
  | `timeout` | derived deadline hit | abandon, cost recorded |
  | `infra` | disk/permission/device errors | retry once |
  | `llm_api` | agent-call failure | backoff ×4 → rotate model → degraded mode (hand-written hypothesis bank; loop keeps running without LLMs) |

- **Watchdog**: the runner already heartbeats; add the inverse — a monitor that
  kills and classifies any child whose progress is stale (AgentX fingerprints
  the log tail; heartbeat age is our equivalent and is already in the schema).
- **Every abandonment is legible**: a `failure` event with class and attempt
  (`given_up:nan_loss` style); a retry is a new attempt event, its cost counted
  against the node; nothing is edited retroactively. This is what makes the
  Reliability tab's "recovered without a human" number real.
- **The loop never wedges**: per-node attempt cap of 3 → node retired, queue
  continues; any unhandled exception in a round is caught, emitted as
  `failure(class=harness_bug)`, node retired, loop continues; `run_ended` is
  written in a try/finally. After the first promotion a valid submission file
  always exists on disk (MLE-bench's top failure mode is "never produced a valid
  submission" — never be that run).

**Deliberately skipped from these papers** (right for Tencent/Kuaishou, wrong for
one week): SGPO prompt self-evolution and paired replay; the four-model judge
ensemble (one cheap LLM rank is enough at K≤3); online guardrail-veto machinery
(no live traffic); expert-panel supermajority voting. AgentX's falsifiable
attribution (declare expected observables, refuse unattributed gains) is the
grown-up version of our leak audit — steal it at step 10 if time allows, as one
optional `expected_observables` field on Hypothesis checked against
report.progress output.

## Execution order from here

3 (synthetic + template; contract rules written) → 4 (runner; retry table +
watchdog + classifier) → 5-minimal → 6 (tree + resume) → 7 (agents; semantic
check + K-candidates) → 8 (ingest + aliccp) → 9 (outputs + audit) →
10 (rulebook; optional falsifiable attribution). The fallback demo stays step 6.
Break-and-fix beats spec-and-stall from here on: the log is the contract, so
anything behind it can be rewritten cheaply.
