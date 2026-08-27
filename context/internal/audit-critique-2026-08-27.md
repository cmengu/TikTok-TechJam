# Critique: frontend↔backend audit + chronological Harness Decisions

Written 27 Aug 2026 by the planner/reviewer session. Internal. Not a spec — a list of
places where the two documents contradict each other, contradict shipped code, or leave
an edge of the loop undrawn. Each item ends with a recommendation so the implementing
agent can act without re-deriving.

State of the repo when written: PR #1 merged (16 event types, schema_version=1, 5 rungs,
9 states, 4 cost slices, 6 failure classes). Phase 2 committed locally on
`phase-2-fake-run-server` (fake_run, SSE server, reducer) against that same vocabulary.

Verdict up front: the audit's diagnosis is right ("the log records what happened, never
what it is doing") and its four backend fixes are cheap. The chronological doc is a
better reading order than the feature-ordered one. But together they introduce three
numbering systems, two incompatible promotion ladders, several event types their own
code emits but their own vocabulary does not contain, and at least four loop edges that
are described in prose and absent from the diagram and the code.

---

## 1. Contradictions with shipped code and the build plan — resolve before phase 3

**1.1 Event vocabulary: 16 vs 22 vs 25 vs 27.**
Code has 16. Chrono doc's `EVENT_TYPES` has 22 and `schema_version: 2`. The audit adds
`phase_entered`, `phase_exited`, `digest` (25). The chrono doc's own phase-13 code emits
`convergence` and `prediction`, which are in nobody's vocabulary (27) — its own
`assert type in EVENT_TYPES` would fail on them.
→ One small PR after phase 2 merges: extend `EVENT_TYPES` to the full 27, keep
`schema_version=1` (nothing has consumed v1 outside this repo, a bump buys nothing),
extend `fake_run.SCRIPT` so `test_covers_every_event_type` still passes, and add the
reducer cases. Do this before phase 3, because every later phase emits from this list.

**1.2 Heartbeat routing.** Chrono 2.4 keeps `heartbeat` in `EVENT_TYPES` and routes it
inside `_drain`. The shipped decision (phase-2 answers) is the opposite: `emit("heartbeat")`
raises, sidecar only via `log.heartbeat()`.
→ Doc follows code. Drop `heartbeat` from the vocabulary in the doc.

**1.3 Two promotion ladders.** The build-phases plan (§6 constants, what phase 5
`measure.py` will be built from) uses: screen reject −0.010 / promote +1·SD(Δ); k=3 means
0.025/0.016; BH q=0.10; t 2.92/2.13/1.83; DiD 0.013/0.007; η=0.005. Chrono phase 11 uses:
screen +1σ / −0.01, replicate "all three deltas positive AND mean ≥ 0.010", holdout η=0.005,
audit at 5σ_full — no BH, no t-stat, no DiD.
→ Pick one. Recommendation: the chrono rule (simpler, honest about its 6–12% FP rate,
matches the audit's dossier screenshot). Then rewrite the build plan's phase-5 constants
to match, or the implementing agent will build the other one.

**1.4 Chrono 4.5 says "derive thresholds from σ", chrono 4 code hardcodes
`promote_bar: 0.010`.** Internal contradiction in one function.
→ `promote_bar = max(0.010, 2.5 * sd_delta / sqrt(3))` and log both terms so the report
can say which one bound.

**1.5 Rung count.** Code has 5 rungs (smoke, screen, full, replicate, holdout). Chrono 11
describes three rungs (screen, replicate, holdout), 13.7 says "four-rung ladder", and
`full` is used only in calibration (phase 4). Yet the Replication tab needs
"screen versus full" pairs per node — so a full-data run must happen somewhere in the
ladder, and phase 11 never says where.
→ Define: replicate = 2 more paired seeds ON THE FULL RUNG (that is what makes the
screen→full pair exist). Keep `smoke` as a 1-minute contract check before screen. Say
"four rungs: smoke, screen, replicate(full), holdout" everywhere.

**1.6 Cost slices.** Four slices: researching, coding, training, tuning. Phase 9 verify
calls `llm_strong.semantic_match`; phase 11 `adjudicate` calls an LLM per link; phase 12
has an adversarial falsifier LLM. None of these is researching, coding, training or
tuning.
→ Map explicitly: verify → `coding`; adjudicate and falsifier → `researching`. Or add a
fifth slice `judging`. The cost tab's headline ("94% of wall-clock at zero agent cost")
depends on these being counted somewhere.

**1.7 `protocol_hash` length.** Chrono 0 truncates to 12 hex; shipped code emits
`sha256:<64 hex>`. Pseudocode only, but the fake fixture and every doc example should
use the shipped form.

---

## 2. Loop edges that are described in prose but missing from the diagram and code

**2.1 UNCLEAR attribution has no edge back to phase 8.** 11.6 says a positive delta with
UNCLEAR attribution does not promote and the verdict is `inconclusive`. 11.5 says
inconclusive nodes return to the queue at reduced priority. But an UNCLEAR attribution is
an implementation defect (dead gate, Glorot init), not noise; re-running the same code
with more seeds reproduces the same dead gate. AgentX's own example fixes it by a
one-line rewrite in round two — that is an edge 11 → 8 carrying the observable finding,
and it does not exist in the loop.
→ Add it: verdict `inconclusive` with `attribution="unclear"` requeues the hypothesis
with `maturity="probe"` and attaches the broken-link report as coder context. Distinct
from noise-inconclusive, which requeues unchanged.

**2.2 What state is a node whose K candidates all failed verify?** Phase 9 `fail_round`
after 3 rewrites. The node was created (candidates_generated carries `node=18`), never
ran, has no measurement. None of the nine states fits: it is not `rejected` (no
measurement), not `retired` (family not dead), not `debugging` (no failure event).
→ Either create the node only after a candidate passes verify (then failed rounds are
hypothesis-level events with no node), or add the rule "rejected with
reason=semantic_failure". The first is cleaner and matches NOVA's "working state
unchanged, round recorded as semantic failure".

**2.3 Admission gate "≥2 independent runs" is unreachable in a hackathon.** 12.3
requires evidence from two independent runs before an anti-pattern is confirmed. If
"run" means harness run (one 24-hour execution), a hackathon has one or two, so the
forbidden list is empty by construction — and the audit's own daily check ("if the
forbidden list is empty after fifty attempts, the gates are not admitting anything")
fires on every run.
→ "Run" here must mean node. Confirm at ≥2 nodes in the same family with the same
failure signature.

**2.4 Where does the adversarial falsifier run?** 12.3 introduces an agent whose only job
is to falsify a claimed mechanism. It appears in no diagram, no code, no cost slice, and
no cadence (after every verdict? batched per round?).
→ Cheapest honest version: run it once per candidate anti-pattern at the moment the
second node matches; one LLM call; slice `researching`; emit `anti_pattern` event with
status. Or cut it and admit anti-patterns at ≥2 nodes only, and say so.

**2.5 Tuner trials are runs but are not in the ladder.** Phase 8.6 sends independent knobs
to Optuna. Each trial is a phase-10 execution and a screen measurement. Are trials nodes?
Do they get seeds? Twenty trials on the screen rung is twenty draws from the same null,
and the best one is the same best-of-N artefact phase 4 warns about.
→ A tuner sweep is ONE node; trials are `measurement` events with `trial=` on that node;
only the best trial enters the ladder at replicate, and it enters with the multiplicity
recorded (`n_trials=20`) so the report can discount it.

**2.6 Restart / resume is not a phase.** Chrono 2 says "nothing else holds state", but
tree, queue, memory and the tuner study all live in-process. The harness will die at
least once overnight. Is a restart a new run (new run_id, index row) or a resume (same
run_id, reduce events to rebuild state)? Nothing says.
→ Resume. `python -m harness resume <run_id>` rebuilds tree/queue/memory by reducing
`events.jsonl` (the same fold the app does — a strong argument the fold is correct), emits
`intervention` if a human triggered it, and re-opens the log. This is the single most
likely hackathon-night failure and it costs one afternoon.

**2.7 Holdout budget arithmetic does not close.** 11.4: five paired seeds, at most twice.
Paired = candidate + incumbent = 10 full runs per holdout visit, 20 for two visits. Phase 4
prices 5 full baseline runs at ~15 GPU-hours, so one full run ≈ 3 h and the holdout costs
≈ 60 GPU-hours — more than the whole hackathon budget.
→ Either holdout uses 3 paired seeds (18 h, still large) or the incumbent's holdout scores
are cached from its own promotion so only the candidate side runs (5 runs, 15 h per
visit). Say which. Also emit a `holdout_visits` counter so the "at most twice" rule is
enforced by code and visible in the app, not remembered by a person.

**2.8 Where do search_validation and holdout come from?** 0.5 carves two validation sets;
1.7 says Ali-CCP has no timestamp and the temporal split is at file level. If the
organisers' file split is train/test only, both validation sets must come out of
`train` — reducing training rows — or `test` doubles as search_validation and the holdout
comes from train (backwards in time, if sample_id is chronological). The two sections
never meet.
→ Decide after the 28 Aug webinar. Until then write into `protocols/aliccp.yaml`:
`search_validation = organisers' test file`, `holdout = last 10% of train by sample_id,
ASSUMED chronological`, and hash the assumption (1.7 already says to).

**2.9 Synthetic planted effect is below the ladder's own power.** 3.3 plants a true effect
of +0.010. Phase 4 says a k=3 paired comparison detects roughly 2.5·SE, and 11.3 promotes
at mean ≥ 0.010. A true +0.010 effect sits exactly at the bar, so the ladder promotes it
about half the time. The build plan's phase-5 gate (`FN=0` on the scorecard) is therefore
unreachable by design, and the scorecard will report ~50% false negatives on a working
harness.
→ Plant +0.025 for the signal feature (≈2.5× the bar) and add a second, marginal +0.010
feature whose expected promotion rate is stated as "≈50%, by design". Change the phase-5
gate to `FP=0, FN=0 on the strong signal, leak caught`.

**2.10 Saturation signature is over the wrong key.** 12.7 hashes "discretised
architecture fields". 5.7 says architecture is worth ~0.002 here and most hypotheses will
be features / objective / training changes. Architecture fields will therefore repeat
>80% almost immediately and the run stops on idea exhaustion while ideas are still fresh.
→ Signature over `(stage, mechanism)` keys of the last N hypotheses, not architecture.

**2.11 Exploration reserve uses unseeded randomness.** 7.5 `random() > explore` in a
harness whose whole argument is replayability.
→ Seed from `protocol.run.seed`; emit `queue_reordered` with `explored=True` when the
reserve fires so the app can show it.

---

## 3. Log → app links the audit introduces but does not close

**3.1 `phase_entered` with no `phase_exited` lights a chip forever.** A worker that dies
mid-phase never emits exit. The strip then shows phase 10 "running" for the rest of the
night.
→ Two rules in the reducer: a phase is open only while its worker's last heartbeat is
under 3× the heartbeat interval; and heartbeats carry `phase=` so the strip can be
rebuilt from the sidecar alone if events lag. Emit `phase_exited` from a `finally:` block.

**3.2 The strip is per-worker, not global.** The researcher can be in phase 6 for node 19
while the GPU worker is in phase 10 for node 18. "Accent for currently executing" as a
single colour cannot show two lit chips with different owners.
→ Reducer state: `active_phases: {worker: {phase, node, since}}`. The chip shows a small
worker badge; the now-running panels below already exist per worker.

**3.3 Fourteen chips mix one-time setup with the loop.** Phases 0–4 happen once; phase 2
(the event log) is never "entered" at runtime at all. After hour two, five chips are grey
forever and read as broken.
→ One "setup" chip (0–4, green once calibrate completes) plus eight loop chips (5–12) plus
"report" (13). Ten chips.

**3.4 Cost on `phase_exited` double counts.** 2.5 puts cost on every event. If
`candidates_generated` carries `cost=` and `phase_exited` also carries `cost=`, the
four-way sum counts coding tokens twice.
→ Cost lives on leaf events only. `phase_exited` carries `duration_s` and nothing else;
per-phase cost is the sum of leaf events between entered and exited for that worker.

**3.5 The `digest` event does not feed the Memory tab it was invented for.** The tab wants
anti-patterns with run counts and admission status. The digest carries only forbidden ids.
→ Add an `anti_pattern` event emitted on create and on every status change
(`pending → contested → confirmed | excluded`, with `runs_seen`). Memory tab = fold over
`anti_pattern` + latest `digest`.

**3.6 No endpoint serves diffs, reasoning files or observable series.** The dossier needs
`patches/node-018-cand2.diff`, `reasoning/node-018.md`, and (by the audit's own argument
that a paragraph does not belong on a JSONL line) observable time series, which are far
larger than a paragraph. No doc defines the endpoint.
→ `GET /runs/{id}/files/{path}` with an allowlist of three prefixes: `patches/`,
`reasoning/`, `observables/`. Observables written as `observables/node-018-seed0.jsonl`;
the `observable` event carries the path and a 3-number summary (first, last, max).

**3.7 `rule_trip` and `semantic_filter` are two names for one thing — or two things
nobody separated.** Chrono 9.7 says every verify rejection emits `rule_trip`; the audit's
`semantic_filter` event carries the same category. The Reliability tab shows "rule trips";
the audit's rejection histogram shows "the seven categories".
→ Split by when they fire: `semantic_filter` = pre-execution candidate rejection
(categories A–F, Z); `rule_trip` = runtime rulebook violation by a running child
(attempted holdout read, protocol write, stdout-only result). Different histograms,
different tabs.

**3.8 Winner diff stored twice.** 2.6 derives `patches/node-018.diff` from `git diff
parent..node`; the audit writes `patches/node-018-cand{0..3}.diff` before ranking. The
selected candidate's diff then exists as a loose file and as a commit.
→ Losers are loose files only. The winner's `cand{k}.diff` is kept as-is and
`node-018.diff` is a symlink or the `diff_path` on `candidate_ranked` just points at the
`cand{k}` file. One source.

**3.9 The one-screenshot dossier needs the fake run to script it.** Part 5's judge
screenshot (rejected promotion, four candidates, seed 0 +0.009, mean +0.003) can only be
demonstrated before real GPU time if `fake_run.SCRIPT` contains exactly that node. The
shipped SCRIPT covers 16 types and no candidates.
→ When the vocabulary PR (1.1) lands, add "node 18" to SCRIPT verbatim from Part 5 and
make it the fixture the JS test asserts on.

**3.10 Permalink route.** `#/run/<id>/node/<n>` is required by Part 5 and appears in no
phase.
→ Add to the phase-2.5 app work; it is hash routing over an existing reducer.

**3.11 What counts as an `intervention` is undefined.** "Every control is an
intervention" — but restarting after a crash, editing `bank.yaml` between runs, or
changing `run:` budget mid-run are not classified.
→ Definition: any human write to `runs/<id>/`, `protocols/`, or `bank.yaml` between
`run_started` and `run_ended`, plus any restart. Emit with `kind=`.

---

## 4. Naming — three numberings now coexist

Build-plan phases 0–10 (what the implementing agent works from), chrono phases 0–13 (what
the events will carry), audit build steps 1–12. "Phase 2" means the event log in one and
fake_run/server in another; "phase 5" means measurement in one and research fan-out in
the other.

→ Events carry `name=` only (`rank_evidence`, `verify`, `run`, …) and no integer; the
integer is a display concern the reducer can map. In prose: "build phase N" vs "loop
phase <name>". Rename the audit's steps to "app steps". Never say bare "phase N" in a
ticket again.

Also: `stage` is already the six pipeline stages (data, features, …). Do not use it for
loop phases or rungs. `round` (used by `digest`) is undefined — is a round one dequeue or
one full 5→12 pass? Define: one dequeue.

---

## 5. Scope honesty

The chrono doc adds four modules the build plan does not have: `agents/evidence.py`
(phase 6), `verify.py` (phase 9, beyond the rulebook), K-candidate `coder.py` (phase 8),
`memory.py` with admission gates and saturation (phase 12). Together they are roughly
the size of the existing phases 6–8 combined. The audit's own line stands: stop after
app step 7 and there is a competitive submission.

→ Order of value per hour, given the ladder and log already exist:
1. K candidates with deterministic ranking (phase 8 + a cut-down 6 with fixed weights) —
   the biggest ablation number and the dossier's centrepiece.
2. `verify.py` categories B, C, D, F only (columns, protocol touch, anti-pattern regex,
   observables wired) — regexes, no LLM.
3. `digest` + `anti_pattern` events with the ≥2-node admission rule, no falsifier.
4. Evidence α-routing and the adversarial falsifier — only if the above is green by
   Saturday.

Reserve all 27 event types now regardless; a reserved type that is never emitted costs
nothing and an unreserved one costs a reducer rebuild.

---

## 6. Decisions — LOCKED 27 Aug 2026

Resolved one by one with the user after the critique above. Where a decision differs from
the item's original recommendation, the decision wins.

### Vocabulary (1.1, 1.2, 1.6, 3.4) — 33 event types, schema_version stays 1
Walking every tab as consumer and every phase as producer found five events nothing
emits, plus one escape valve. `heartbeat` is out (sidecar only).

- run: run_started, run_ended, intervention, convergence, saturation, prediction,
  submission_written, **data_profile** (new: phase-1 counts/ingest hash), **note** (new:
  free text + subject, feed-only — the 3am valve)
- phase: phase_entered, phase_exited
- research: **research_query** (new: parent of sources), research_source, cache_lookup
- hypothesis: hypothesis_queued, **hypothesis_updated** (new: status ∈ backlog/probe/ready/
  dequeued/spawned/failed_verify/dropped/merged), queue_reordered
- candidate: candidates_generated, semantic_filter, candidate_ranked
- node: node_created, state_changed, measurement, observable, attribution, verdict,
  **incumbent_changed** (new: node + reason ∈ promotion/rollback), failure, recovery, rule_trip
- memory: digest, anti_pattern
- cost: **llm_call** (new: the ONLY token-bearing event — slice, model, tokens, node,
  purpose; gpu_s lives only on measurement/failure; `cost=` removed from everything else)

Rules: strict writer (emit rejects unknown types), lenient reader (reducer ignores and
counts unknown types) — adding a type is never a breaking change. Every event names its
subject (node= / hyp= / cand= / worker=). Paths end in `_path`, relative to run_dir.
Slices on llm_call are set by the caller: researcher, brief, adjudicate, falsifier →
researching; coder, verify semantic match, debug turns → coding; tuner → tuning;
training is GPU-only.

### Ladder (1.3, 1.4, 1.5, 2.7, 2.9) — chrono rule, four fixes
- Rungs: smoke → screen → replicate-on-full. Holdout is NOT a rung.
- Refuse to search if σ_full > 0.02.
- sd_delta default = σ·√2 (ρ=0); re-estimate ρ after 3 replicated candidates; emit band
  refresh as measurement stage=calibrate.
- Screen (1 paired seed, subsample): Δ0 ≥ +1.0·sd_delta_screen → replicate;
  Δ0 ≤ −0.010 → rejected; else inconclusive (priority ×0.5, ≤2 revisits, then retired).
- Replicate (3 paired seeds ON FULL; incumbent's seeds 0–2 cached from its promotion):
  all 3 > 0 AND mean ≥ bar, bar = max(0.010, 0.95·sd_delta_full) — one-sided known-σ
  α=0.05 at k=3; with the sign rule ≈3% per-candidate false promotion. Say so in writeup.
- mean ≥ 5·sd_delta_full → leak audit first (single-feature AUC 0.90 + three other checks).
- Attribution CLEAR required; UNCLEAR → hypothesis_updated status=probe with
  context_path=reasoning/node-NNN-links.md.
- Promote → verdict promoted + incumbent_changed reason=promotion.
- Holdout: run-level checkpoint, ≤2 visits (first promotion + end), 3 paired seeds,
  candidate side only, `holdout_visits` counter enforced in code. Report new number only
  if ≥ best_holdout + 0.005; a node failing holdout is rejected reason=holdout, never
  requeued.
- Dropped from build plan §6: BH q=0.10, t-table, DiD, k=5 tier.
- Synthetic: plant +0.025 strong, +0.010 marginal, 0 noise, leak. Phase-5 gate: strong
  promotes, noise never, marginal 30–70%, leak caught, holdout_visits never reaches 3.

### Lifecycle (2.1, 2.2, 2.5) — three objects, three lifetimes
- Hypothesis lives in the queue: backlog → probe → ready → dequeued → (spawned |
  failed_verify); plus dropped, merged. Every transition = hypothesis_updated.
- Candidate exists only between candidates_generated and candidate_ranked, addressed
  hyp=,cand=. K candidates, ≤3 rewrite rounds, then failed_verify. No node.
- Node is born when the ranked winner passes verify: node_created(hyp, cand,
  parent=incumbent, diff_path). Only nodes have measurements/states/verdicts. Nine states
  unchanged. Writer rule: node_created must reference a hyp currently `dequeued`.
- UNCLEAR attribution = probe requeue with link report in coder prompt; noise-inconclusive
  = same hypothesis requeued ×0.5, no context. Two distinguishable edges.
- Tuner sweep = one hypothesis (stage=training, mechanism=hparam-sweep) → one node;
  trials = measurement(rung=screen, trial=i); best trial enters replicate with n_trials.
- Dossier candidates section folds by hyp=, so it renders for hypotheses that never
  became nodes.

### Memory (2.3, 2.4, 2.10, 3.5)
- "Run" = node. anti_pattern confirmed at ≥2 nodes same family + same failure signature;
  1 node = pending. Status ∈ {pending, confirmed, excluded}; excluded set by hand
  (intervention). Falsifier CUT; revisit Saturday only if green.
- Saturation: signature over (stage, mechanism) of last 20 hypotheses; stop when repeat
  rate > 80% for 2 consecutive rounds. Round = one dequeue.
- Memory tab = fold over anti_pattern + latest digest.

### Run mechanics (2.6, 2.8, 2.11, 3.11)
- `python -m harness resume <run_id>`: reduce events.jsonl → tree/queue/memory, reopen
  log with seq continuing, emit intervention kind=resume. Optuna study in runs/<id>/tuner.db.
- Splits until webinar: search_validation = organisers' test file; holdout = last 10% of
  train by sample_id, assumption written and hashed. Revisit 28 Aug.
- Exploration: random.Random(protocol.run.seed); queue_reordered explored=true.
- Intervention = any human write under runs/<id>/, protocols/, bank.yaml during a run,
  plus resume; kind= field.

### App (3.1–3.3, 3.6–3.10)
- phase_exited in finally:; reducer closes a phase if its worker's heartbeat is >3×
  interval old; heartbeats carry phase=; active_phases keyed by worker, chip shows badge.
- 10 chips: setup, fan-out, rank, queue, candidates, verify, run, believe, digest, report.
- GET /runs/{id}/files/{path}, allowlist patches/ reasoning/ observables/; observables as
  per-seed JSONL, event carries path + first/last/max.
- semantic_filter = pre-execution (A–F, Z); rule_trip = runtime child violation.
- Losers are loose files; winner's cand{k}.diff is the one file; no node-NNN.diff.
- fake_run scripts "node 18" verbatim from audit Part 5 = the JS fixture.
- Hash route #/run/<id>/node/<n>.

### Naming (§4)
Events carry loop-phase name= only, no integer. Tickets say "build phase N" / "loop phase
<name>". `round` = one dequeue. `stage` = the six pipeline stages only.

### Next concrete action
After phase 2 merges: one PR "vocabulary v1 complete" (33 types, note valve, strict-writer
/ lenient-reader tests, fake-run node 18, files endpoint, hash route). Then rewrite
build-plan §6 with the ladder constants above before build phase 5 starts.
