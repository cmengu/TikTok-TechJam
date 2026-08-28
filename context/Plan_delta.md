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

---

## 27 Aug, session 2 — locks made in chat, now written down

Recorded after the fact by the planner session. Everything here was decided in
conversation with the human on 27 Aug while phases 3–4 were being built; none
of it was in the plan page or this file until now. Items marked **B to review**
were built by the planner session without owner B and are open to be reshaped.

### Phase 4 policy (confirmed by the human)

- Failure class names stay as in `types.py`: `cuda_oom, host_oom, diverged,
  timeout, contract_violation, crash`. `stall` is added as a class. `infra` and
  `llm_api` wait for step 7 (nothing can raise them before an LLM exists).
- `diverged` → **abandon**, no LR÷2 retry (a NaN at the same config is
  deterministic; a retry spends a run to learn nothing). Class name unchanged.
- `classify` treats returncode `-9` and `137` as the same `host_oom`; the
  `failure` event carries `137`.
- `host_oom` recovery = halve `BATCH` (same knob as `cuda_oom`). Never add
  `LOADER_WORKERS` to the template — it has no DataLoader, the knob would be fake.
- Stall watchdog ships in phase 4: no new progress line for
  `max(5 min, 3× median step gap)` → kill, retry once.
- Runner must absolutize `TaskPaths` in `_build_env` — the child runs with
  `cwd=workspace`, so a relative data path crashes with `FileNotFoundError`.
  (Worked around in `run-one` only; still open in `runner.py`.)

### Phase 3 locks (confirmed by the human; being applied on `fix/phase-3-review`)

- `harness/candidate/rules.jsonl` is the one rules file: one JSON object per
  line — `id, statement, check ("static"|"llm"), pattern (regex|null),
  mode ("forbid"|"require"), severity ("fail"|"warn"), source`. Seeded with the
  seven contract clauses from §5 above; step 7 copies it to
  `runs/<id>/rules.jsonl` and appends root-caused rules with `source: "node NNN"`.
  No separate CONTRACT.md. Distinct from phase-10 R1–R6.
- `prepare()` computes real sha256 of the written parquets and raises on
  mismatch against `synthetic.yaml` when the yaml value is not a `000…`
  placeholder. Fill the yaml once at the phase gate. Pin `pyarrow==<installed>`,
  write with fixed compression and no user metadata (footers embed the writer
  version). `script_sha` hashes only `score()`'s source, not the whole file.
- Four planted effects, not three: `f_true` (single-feature CVR AUC on clicked
  rows ≈ 0.65, band [0.60, 0.72]), `f_marginal` (≈ 0.56, band [0.53, 0.60]),
  `f_zero`, `f_leak` (> 0.90). Retune against 1M rows; if phase 5's scorecard
  later misses +0.025 at the model level, adjust the planted size, never the bar.
- scikit-learn is a dependency; `roc_auc_score` is the AUC, guarded by a
  10-row hand-computed fixture test. `score()` joins preds on `sample_id`,
  asserts id-set equality and no duplicates.
- Base features = `user_id, item_id, cat_a, cat_b, cat_c`; `hist` excluded in v1.
- `n_impressions` is a `SyntheticTask` constructor arg (default 1M); no env override.
- Capability: the candidate must not import `harness.*`. `report.py` moves to
  `candidate/report.py` at repo root, `template.py` does `import report`, the
  runner copies both into the workspace and spawns `python template.py`.
  `report.checkpoint.save` takes bytes (template does `torch.save` to a buffer).
  Template does not self-score (`metrics={}`); `task.score()` is the only
  numeric entry.
- Failure injections fire at the matching moment (mid-training at
  `total // 2`; `hang` after the first real progress line), not before data load.
- Tests: `crash` asserts returncode == 1 exactly; `oom_host` accepts `-9` or
  `137`; `hang` kills in `finally`; `slow` deselected by default in pyproject.

### Added without a ticket (PR #6, merged) — **B to review**

- `python -m harness run-one [--fail MODE] [--rows N] [--seed S] [--timeout T]
  [--heartbeat S]` in `harness/__main__.py`: the phase-4 manual gate as a
  command. Creates its own run (EventLog always opens with `run_started` at
  seq 1, so an existing run id cannot be reused), uses a demo protocol with
  placeholder hashes when `--rows != 1_000_000`, emits `node_created` itself
  (a phase-6 event, standing in for the tree), prints the app URL. Test:
  `tests/test_04_cli.py`. Phase 6 should replace the `node_created` emit with
  the tree's own.
- App (owner B's phase-2 views, changed by the planner session): a fourth
  "Event log" panel (`log` array in the reducer, last 200, heartbeats
  excluded); "Now running" renders the runner's `step/total/loss/attempt` as
  well as the fake run's `status/progress`; with no `?run=` pinned the page
  polls `/runs` every 2 s and switches to the newest run. Reason: the phase-4
  gate says "watch the failure/recovery pair appear in the app", but the
  reducer had no case for `failure`/`recovery` and the tree only lists
  `node_created` nodes. B may fold the log panel into a proper view or keep it
  as the raw feed.

### Branch order for the review fixes

`fix/phase-3-review` (blocks 4 and 5) → `fix/phase-2-review` (SSE partial-line
buffer, cwd-relative `runs/` path, fake-run wipe guard, `lastSeq` split; plus
the two one-liners: drop the nested lock in `events.py`, `STATES =
get_args(State)`; nothing else) → merge `main` into whatever phase-4 follow-up
exists. Merge, don't rebase, branches that have a PR.

---

## 28 Aug, session 3 — precedence, deferrals, and the 9-before-8 reorder

Recorded after a two-axis review of phase 7 found drift that traced back to this
file disagreeing with `Build_phases.html` about what lands when. Nothing here is
new design; it resolves an ambiguity that already cost a day.

### Precedence — the rule that was missing

**`Build_phases.html` phase pages win on *what ships when*. This file wins on
*how*.**

- Sequencing, per-phase in-scope file lists, named tests and gates come from the
  phase page. It is the executable document.
- Mechanisms and cross-cutting rules come from here: §1 event seam, §2 ranking
  arithmetic, §3 replay, §6 retry table and classifier. These hold in every phase
  that touches them.
- **§5 is the exception that caused the trouble.** It is the only section that
  makes scheduling claims ("Lands with step 7", and the execution order at the
  end). Those claims are **advisory, not binding**. §5's *mechanisms* are binding
  when the phase page schedules them; §5's *timing* is not.
- Consequence, stated plainly: phase 7 ships complete against `#p7` and
  incomplete against §5. That is the intended outcome, not a gap to close.

Precedence on numbers is unchanged: Audit Redline §6 > `Build_phases.html` >
Harness Decisions.

### `contract.py` — the concrete case

`harness/agents/contract.py` was built in phase 7 under §5's authority, but the
phase page puts static leak checks in phase 10 (`R5_static_split`,
`R6_static_target`, severity **warn**, "never blocks"). It stays — deleting
working code for document purity is waste — but it splits by severity:

- **Capability path checks stay blocking.** `protocols/`, `measure.py`,
  `rulebook`, `holdout` in a prompt or diff is a lock violation, not a heuristic.
- **Leakage heuristics become warn-only** per phase 10 (`train_test_split(`,
  label-column reads). They emit `rule_trip` with severity `warn` and never stop
  a diff reaching the runner.
- `candidate/rules.jsonl` is currently read by nothing; `contract.py` hardcodes
  its patterns instead. Wiring the file in is deferred with the rest of §5 below.

### Deferred until after the first real run

These are §5/§6 items that need real failures to tune against. NOVA's and
AgentX's numbers come from production systems with thousands of runs; we have
seventeen, all synthetic, with effects we planted ourselves. Building them now
means building them blind.

- **K candidates per expensive run** (§5) — K=2–3 diffs at full/replicate, rank
  and pick one.
- **LLM review of the diff** (§5) — the second half of the verification cascade;
  static greps ship, the review does not.
- **Rules accumulate from confirmed errors** (§5) — copy `candidate/rules.jsonl`
  to `runs/<id>/rules.jsonl`, append root-caused rules with `source: "node NNN"`.
- **Structured trajectory feedback** (§5) — NOVA's weak-components / directions /
  forbidden headings. `lessons.jsonl` keeps the flat `#p6` row for now.
- **Falsifiable attribution** (§5 tail) — `expected_observables` on Hypothesis,
  still phase 10 and still optional.

### The one exception — degraded mode

`llm_api` failure class: backoff ×4 → rotate model → fall back to the
hand-written bank so the loop keeps running without LLMs (§6). This is demo
insurance, not search quality, and it is cheap.

It is **out of scope for the phase-7 cleanup pass** — it needs a new failure
class in `runner.py`, which is outside `#p7`'s in-scope list, and that is exactly
how phase 7 drifted the first time. It lands as its own small PR **between phase
9 and phase 8**, so it is in place before iteration 0 and before the demo.

`infra` as a failure class ships with it.

### Execution order correction

The order at the end of §5 reads `… → 7 (agents) → 8 (ingest + aliccp) → 9
(outputs + audit) → 10`. **Phase 9 now comes before phase 8.** The full argument
is in `context/Handoff.md`; in short, `#p9`'s audit tests run against the fake-run
stream, its gate is the phase-6 fallback plus a synthetic run, and
`test_convergence_rule` supplies its own ε and N — so only the submission column
list and the real ε/`n_rounds` need the organisers, and both are config rather
than code. Phase 8 is blocked on the organisers' webinar for seven `pending`
values in `aliccp.yaml` and on data that is not downloaded, and building the
audit tab first means iteration 0's GPU spend is instrumented while it runs.

Phase 10 is genuinely blocked behind phase 8: `POS_TOL` can only be set from an
observed real run.
