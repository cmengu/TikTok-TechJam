Beating NISE · backend spec companion · 25 Aug 2026 · §5–§7 revised 26 Aug
Harness Decisions
The ten backend features, one at a time: what the spec already decided, how this is normally done, and the things that bite. Names follow the product spec throughout — the old backend names are shown in grey where they changed.

Sections
A · Files and how they connect
0 · The one principle
1 · Protocol — defining the ruler
2 · Data layer
3 · Rulebook
4 · Event log
5 · Runner
6 · Measurement
7 · Run tree & Hypotheses
8 · Agents
9 · Audit & outputs
10 · Synthetic benchmark
11 · Naming standard
A · Files and how they connect
Read this section first. Every file below is either frozen (its values come from the organisers' brief, it is locked and hashed before the search starts, and nothing the agent controls can write to it after that), part of the search loop (decides what to try next), part of execution (runs one attempt and measures it), or part of the truth-to-view path (the log and the app). Judgement lives only in the frozen and measurement files; everything else is plumbing that can be wrong cheaply.

FROZEN BEFORE THE RUN
SEARCH LOOP
EXECUTION
TRUTH → VIEW
protocols/
synthetic.yaml · aliccp.yaml
harness/protocol.py
data/
ingest.py · schema.py
subsample.py
parquet cache
harness/tasks/
base.py · synthetic.py
aliccp.py
harness/agents/
researcher.py · brief.py
cache.py
harness/tree.py
the loop · queue · node states
agents/coder.py
agents/tuner.py
harness/runner.py
candidate subprocess
candidate/template.py
+ candidate/report.py
harness/measure.py
band · ladder · leak audit
harness/outputs.py
submission · registry · report
harness/events.py
+ fake_run.py (scripted stream)
runs/<run-id>/
events.jsonl · heartbeat.jsonl
app/server.py
+ harness/audit.py
+ reference/published_costs.yaml
browser (app/)
load · canonicalise · hash
protocol_hash
parse once
read split
train + search-val only
hypothesis (schema-checked)
diff ↑
↓ dequeued
tuner shortlist ↑
run node
spawn · timeout · DEVICE
result.json
verdict → rerank
promoted → write submission
append + flush
tail ?since=seq
SSE → reduce(events)
every module reports to events.py — never to each other's state
harness/types.py (Hypothesis · Node · RunResult · Verdict) is imported by every box and drawn nowhere
Every file in the tree below appears in this map (checked by script). Solid boxes are code you write; dashed boxes exist at run time — data, a child process, a directory. The blue box is the only orchestrator. The bottom bus is the rule that every module reports to events.py and never to each other's state.
Repository layout
Same tree as §11, with the files the walkthrough talks about but the old tree forgot: the candidate template and its contract library (§5), the shared types file (the two-person seam, below), a scripted fake run so the app can be built on day one (§4), and the tiny server that streams the log. rulebook.py is gone from the tree on purpose — see §3 and step 10 of the build order.

beating-nise/
├── data/                  ingest.py, schema.py, subsample.py
├── harness/
│   ├── types.py           Hypothesis, Node, RunResult, Verdict — the only file both people edit   ← NEW
│   ├── protocol.py        load protocols/*.yaml → canonical bytes → protocol_hash
│   ├── events.py          single writer, node-id allocator, events.jsonl + heartbeat.jsonl
│   ├── fake_run.py        emits a scripted schema-v1 event stream so the app has data on day one  ← NEW
│   ├── runner.py          spawn candidate, timeout, failure classes, recovery
│   ├── measure.py         noise band, ladder, leak audit, promotion decision
│   ├── tree.py            THE LOOP: queue → coder → runner → measure → rerank
│   ├── audit.py           read-only projections: replication, cost, reliability
│   ├── outputs.py         submission writer, convergence counter, registry, report
│   ├── candidate/         template.py (what the agent edits) + report.py (what it imports)   ← NEW
│   ├── agents/            researcher.py, coder.py, tuner.py, brief.py, cache.py
│   └── tasks/             base.py, synthetic.py, aliccp.py
├── protocols/             synthetic.yaml, aliccp.yaml
├── reference/             published_costs.yaml
├── runs/                  <run-id>/events.jsonl, heartbeat.jsonl, patches/, workspace/ (git)
└── app/
    ├── server.py          GET /runs/{id}/events?since=N  → Server-Sent Events                 ← NEW
    └── …                  the frontend (product-spec tabs)
Who reads what, who writes what
File	Reads	Writes / returns	Called by
harness/types.py	—	the four dataclasses every other file passes around	everything; changed only by a PR both people review
protocols/aliccp.yaml	— (hand-written)	—	protocol.py
harness/protocol.py	the yaml	Protocol object + protocol_hash	tree, measure, events, outputs, cache, tasks
data/ingest.py	raw Ali-CCP csv	partitioned parquet + ingest_hash	you, once, before the run
data/subsample.py	parquet partitions	a training subsample (never an eval subsample)	tasks/aliccp.py, for the screen rung
harness/tasks/aliccp.py	parquet, protocol split rules, organisers' scoring script	train / search-val paths for the candidate; score(preds) via their script	runner (data), measure (scoring), outputs (holdout)
harness/candidate/template.py	DEVICE, SEED, data paths from env	result.json, checkpoint, progress via report.py	runner spawns it; coder edits a copy of it
harness/runner.py	node's git commit, rung, seed, device	RunResult (metrics, cost, failure class); failure / recovery / heartbeat events	tree.py
harness/measure.py	RunResult, incumbent's paired scores, band	verdict event with the new node state	tree.py
harness/tree.py	verdicts, hypothesis queue	node_created, state_changed, queue_reordered events; calls everything	python -m harness run protocols/aliccp.yaml
harness/agents/researcher.py	brief, incumbent summary, family stats, research cache	one hypothesis JSON (schema-validated) + research_source events	tree.py when the queue is thin
harness/agents/coder.py	a hypothesis + the incumbent's template + last traceback	a diff, committed on the run branch	tree.py on dequeue and on debugging
harness/agents/tuner.py	a node + knob ranges	trial table on the node; shortlist as child hypotheses	tree.py, screen rung only
harness/events.py	a queue fed by every module	events.jsonl, heartbeat.jsonl; allocates node ids	everything; the only process that opens the file for writing
harness/fake_run.py	a script of ~200 events	a real runs/fake-0001/events.jsonl, replayed at 20× speed	you, while building the app
harness/audit.py	events.jsonl	replication pairs, cost by slice, reliability counts (pure functions)	app/server.py, outputs.py (report)
harness/outputs.py	promoted node's checkpoint, holdout via tasks, protocol ε/N	submission file, submission_written, prediction-with-band, runs/index.jsonl	tree.py after every promotion; at run_ended
app/server.py	events.jsonl, heartbeat.jsonl, audit.py	an SSE stream per run + a few JSON endpoints	the browser
Build order
Each step is runnable on its own and on the synthetic task, so you never have a pile of untested modules waiting for the last one. The app moves to step 2: you are right that you want eyes on the backend from the first day, and the log makes that free.

types.py + protocol.py + events.py. Load a yaml, hash it, write a run_started event. You can already tail -f the log.
fake_run.py + app/server.py + the app. A scripted stream of every event type in schema v1, replayed through the real server. The frontend person now has the whole picture — tree, queue, verdicts, heartbeats — before any real backend exists, and every later backend step is watched through it.
tasks/synthetic.py + candidate/template.py + report.py. A fake dataset, a baseline training script that honours the contract, a result.json.
runner.py. Spawn the template, enforce a timeout, classify a forced failure, emit events. Watch it in the app.
measure.py. Run the template five times with five seeds → band. Plant the known-effect feature (§10) and check the ladder catches it.
tree.py with a hand-written hypothesis list. The loop works end to end with no LLM in it. This is also your fallback demo.
agents/. Swap the hand list for researcher → coder. Add the tuner last.
data/ingest.py + tasks/aliccp.py. Only now touch the real data; the protocol yaml gets its hashes filled in.
outputs.py + audit.py. Projections over a log that already exists; the app's Audit tab lights up.
Rulebook checks, late. After the first full Ali-CCP run has shown you what a leak actually looks like here, add the three or four post-checks to measure.py's leak audit. Adding them before you have seen a real run means guessing at thresholds.
Working as two without merging into each other
You have the right instinct, with one correction: the seam between frontend and backend is not "all the API calls between the modules". It is two small things, frozen on day one:

The event schema, version 1 — the fixed vocabulary of event types in §4 and the fields each carries. The frontend never sees a module; it sees events.
app/server.py's handful of endpoints — the event stream, the heartbeat stream, and two or three aggregates from audit.py (cost by slice, replication pairs, reliability counts).
Once those are fixed, everything the app shows is a fold over the stream, so the frontend can be finished against fake_run.py while the backend is still half-built, and nothing the backend does later can break it except a schema change — which is why schema_version is on every line.

For two people both on the backend, split along the bus in the map: one person owns the left and the execution column (protocol, data, tasks, runner, candidate, measure); the other owns the loop and the view (tree, agents, outputs, server). They meet only at the four dataclasses in types.py — Hypothesis in, RunResult and Verdict out, Node for the tree. The way to avoid diff-merging each other is one skeleton commit first: every file exists with its function signatures, its dataclasses, and raise NotImplementedError, plus one test that imports everything. After that commit each PR touches only its owner's files, and types.py changes only by a PR both review.

Who takes which build step
Same split, made concrete against the build order above. A owns the execution column (everything that decides whether a number is believed); B owns the loop and the view (everything that decides what to try next and what the judges see). Each row is a PR by one person, reviewed by the other.

Build step	Person A — execution column	Person B — loop and view
1 · types + protocol + events	protocol.py, the hashing	events.py, the single writer and node-id allocator; both sign types.py
2 · fake_run + server + app	—	all of it; B's day 1–2, and the thing every later step is watched through
3 · synthetic task + template + report	all of it; A's day 1–2, including the three planted effects (§10)	—
4 · runner	runner.py: failure classes, derived timeout, heartbeat	watches it in the app; files schema gaps as issues, not edits
5 · measure	measure.py: rung 0 σ and ρ, the ladder v2, the DiD gap, checkpoint sensitivity, leak audit	the Replication and Audit projections that read the verdict events
6 · tree with a hand-written hypothesis list	—	tree.py: greedy + fork-on-stall, the queue, the lessons file
7 · agents	tuner.py (the Optuna study below) — it lives under the runner, not beside the researcher	researcher, coder, brief, cache
8 · ingest + aliccp task	all of it, including the holdout split that no other module can read	—
9 · outputs + audit	submission writer and its read-back check	audit.py, report, registry
10 · rulebook checks	the post-checks in measure.py's leak audit	Audit-tab rows for rule trips
The pairing that keeps this honest: the person who owns measure.py also owns the numbers in §6, and the person who owns tree.py also owns §7 — so a threshold change and a policy change are each one PR by one person, and neither can quietly loosen the other's bar. A is on the critical path for the fallback demo (steps 3–5); B is on the critical path for the judges (steps 2, 6, 9). Both have something runnable on day one.

0 · The one principle
Everything below is one idea applied ten times: the agent reads, the harness decides. There are three layers, and the rule is that judgement only ever lives in the bottom one.

Agents propose ideas and write code. They can be wrong and it costs a run.
Runner and search execute and schedule. They can be buggy and it costs time.
Protocol, rulebook and measurement define what is valid, what is comparable, and what is believed. If these are wrong, every number the system produces is wrong and nothing downstream can detect it.
The practical consequence: the bottom layer is filled in from the brief before the run — by you, or by an agent you check — then frozen, hashed, and not writable by any process the agent controls. Who types it does not matter; when it stops being writable does. That is the whole reason the Protocol tab sits first in the product spec.

1 · Protocol — defining the ruler was: Benchmark profile
What the problem statement actually gives us
Re-reading the brief, the organisers hand over exactly five things under "Starter Kit" and "Allowed assumptions": a fixed train / validation / hidden-test split; an official baseline with published scores; the evaluation script including the convergence rule (ε, N) and the absolute-delta aggregation; an example submission with an output schema; and the metric definitions with their evaluation populations (CTR AUC over all impressions, CVR AUC over the clicked subset). The compute budget is "TBD".

That list is the protocol. Our job is not to invent one but to make theirs machine-readable, immutable and hashed. The profile fields should map one-to-one onto those five items, so when the webinar fills in the blanks on Friday it is a matter of pasting values, not redesigning.

How this is normally done
There is no single industry standard. None of the four below is a paper that defines "a protocol"; they are four places where careful people ended up with the same shape, and the shape is what we copy. Sources are linked so you can check the fields yourself.

RecBole's eval_args — a software config, not a paper result. It lives in the RecBole "Evaluation Settings" docs: split (ratio-split RS or leave-one-out LS), group_by (None or user), order (RO random or TO temporal), mode (full, uni100, pop100, or labeled for CTR-style data). The library itself is Zhao et al., RecBole, CIKM 2021. Our yaml's splits and metrics blocks are those four ideas written out for Ali-CCP; for us mode is always labeled.
BARS — Zhu et al., BARS: Towards Open Benchmarking for Recommender Systems, SIGIR 2022. Its dataset pages (e.g. Criteo_x4) list an md5sum for train.csv, valid.csv and test.csv, and name preprocessing variants Criteo_x4_001, _002. That is where "hash the split files" and the versioned protocol id come from.
MLPerf — Mattson et al., MLPerf Training Benchmark, MLSys 2020: a fixed reference implementation, a target quality, and a list of hyperparameters submitters may not change. Our baseline block (repo, commit, exact command) is that idea.
Pre-registration — Nosek et al., The preregistration revolution, PNAS 2018: state the analysis before you see the outcome. Our prediction-with-error-bar, logged before the hidden test is scored, is the same move.
The reason any of this matters is Dacrema et al., Are We Really Making Much Progress?, RecSys 2019: most claimed recsys gains vanished once splits, negative sampling and metric cut-offs were held fixed. A protocol object is the defence against doing that to ourselves.

What the organisers actually want, mechanically
Strip the brief to its moving parts and it is one scoring loop that they own, wrapped around an agent that we own. Everything we build sits inside the middle box; everything else is theirs and must be copied exactly, not re-invented.

THEIRS
fixed train / val split
hidden test, never seen
OURS · the agent
any loop, zero touches
stops when Δ < ε for N rounds
writes predictions or checkpoint
THEIRS
eval script, pinned
CTR AUC all · CVR AUC clicked
THEIRS
Δ vs official baseline
score = mean |Δ| over metrics
what judges also read:
tokens + GPU-h · why each idea · interventions
data
submit
score
baseline is the zero point, so a reproduced baseline is where the run starts
Three of the four boxes are the organisers'. The agent only has to do two things their way: stop by their ε / N rule, and hand back a file their script can score.
Two words that get confused, kept apart on purpose:

Step 0 = write the protocol. Copy their five items into protocols/aliccp.yaml and hash it. Nothing runs before this exists, because nothing can be compared before it exists.
Iteration 0 = reproduce the baseline under that protocol. Run their NISE command on their split with our seeds. Its scores are the zero point their scoring subtracts from, so if we cannot reproduce it, every delta we later report is measured from the wrong place. The run refuses to search until this passes.
Until the webinar on 28 Aug
The brief's own note applies: the organisers' actual starter kit did not surface in any public search, so the five items above are what the problem statement says, not what the code does. The fields that stay null in the yaml — ε, N, budget, published baseline numbers, whether the hidden test is the official temporal half or a re-split — are exactly the seven questions listed in the brief's §7. Paste the answers in; do not redesign.

"Hand-written"? No — frozen. The word was wrong.
You are right, and the earlier draft said it badly. Two different things were being called "the protocol": the schema (the shape of the yaml below — which fields exist) and the values (the split hashes, the metric populations, ε, N, the baseline command). The schema is ours and is written once. The values come out of the organisers' brief and starter kit — and yes, an agent can do that extraction at setup time; you dump the brief in, it fills the yaml, you read it once and check it against the brief. What must never happen is a write to that file by anything the search loop controls after the run starts. So the property is "frozen and hashed before iteration 0", not "typed by a human". The column header in the map now says so.

The schema
One decision the backend spec does not make yet: two tiers, not one hash. The fields that define comparability get hashed; the fields that only bound a run do not. Otherwise two runs that differ only in wall-clock budget can never be pooled on the Replication tab.

# protocols/aliccp.yaml
schema_version: 1
task: aliccp                 # adapter name

ruler:                       # everything below is hashed -> protocol_hash
  rulebook_version: 3
  data:
    ingest_hash: ...         # hash of the parquet cache, from the data layer
    train:  {source: sample_train, sha256: ...}
    test:   {source: sample_test,  sha256: ...}   # organisers' hidden test; we never read it
  splits:
    search_validation:  {from: train, rule: "last 10% by sample_id", sha256: ...}
    holdout_validation: {from: train, rule: "preceding 10% by sample_id", sha256: ...}
  metrics:
    ctr_auc: {population: all_impressions, positive: click,      output: p_click}
    cvr_auc: {population: clicked,         positive: conversion, output: p_conversion_given_click}
  scoring:
    script_sha: ...          # organisers' evaluation script, pinned
    aggregation: mean_absolute_delta
  baseline:
    repo: github.com/Hjh233/NISE
    commit: ...
    command: "python run_ali_ccp.py --strategy adaptive_ucvrlc ..."
    published: {ctr_auc: null, cvr_auc: null}   # fill Friday; may stay null
    reproduced: {ctr_auc: [..5 seeds..], cvr_auc: [..5 seeds..]}
  convergence: {epsilon: null, n_rounds: null}   # organisers' values
  seeds: {pinned: [data_shuffle, init, dropout], cuda_deterministic: false}

run:                         # NOT hashed; recorded per run
  budget: {gpu_hours: null, wall_clock_h: null, llm_usd: null}
  workers: 1
Nuances
The gate must be self-referential. "Reproduce against their published number" cannot be the pass condition: there is no published NISE CTR AUC anywhere, and the CVR number depends on split and evaluation space. The gate is: run their command five times under our frozen split, and the noise band is the spread we observe. Their published number, if any, is a sanity check, not the bar.
Declare which head is scored. CVR AUC on the clicked subset is scored on p(conversion | click). An ESMM-style model naturally produces p(click)·p(conversion | click); ranking clicked rows by that product is not the same as ranking by the conditional, and the difference is real. The metric entry names the required output so the submission writer can refuse the wrong one.
Canonical serialisation before hashing. Sort keys, fix float formatting, strip comments, then SHA-256. Otherwise a reordered YAML produces a "different protocol" and nothing pools.
The hash covers the code that scores, not just the config. If the organisers' script changes tie handling or float precision, numbers move. Pin its commit.
Two validation sets, deliberately. The agent searches on search_validation; the harness alone sees holdout_validation. The holdout is what the "searched-on vs never-touched" replication pair is measured against, and it is the only defence against the search overfitting the public validation across fifty hypotheses.
Protocol versions are append-only. Tightening a rule on Wednesday creates aliccp.v2.yaml with a new hash; runs stamped with v1 keep their stamp and stop being poolable with v2. That is the intended behaviour, not a bug.
2 · Data layer
Theirs
The raw files and the train / test boundary. The test file is theirs and is never opened; whatever validation they ship is used as they define it.
Ours
The parquet cache, the search-validation and holdout carve-outs inside train, the subsampler, the feature kinds.
Judges read
Technical (robustness of the pipeline) and Cost — a screen that is a file selection, not a scan, is what makes fifty hypotheses affordable.
What's decided
Parse the raw files once into a columnar cache (parquet); one row per impression; keep sparse, dense and multi-valued features as three distinct kinds; own the subsampler.

How this is normally done
Ali-CCP ships as sample_skeleton_{train,test}.csv (sample id, click, conversion, common-feature index, feature count, feature list) plus common_features_{train,test}.csv, joined on the common-feature index. The feature list is a string with three levels of separator: \x01 between features, \x02 between field id and feature id, \x03 before the value. Field ids are the documented Taobao ones — 101 user, 205 item, 206/207/210/216 item category/shop/intention/brand, 121–129 user categoricals, 301 position, 508/509/702/853 user–item cross statistics, and the four _14 fields (109, 110, 127, 150) which are the user's historical categories, shops, brands and intentions, each a list of ids with weights.

torch-rechub, and therefore NISE, reduces this to 23 sparse columns plus 8 dense columns. The dense eight are the cross statistics and the four history fields collapsed to a single weight each. That is the "discarded structure" the spec refers to.

Nuances
Ali-CCP has no timestamp column. The "temporal" split is at file level — the train file is the earlier period, the test file the later — but within a file there is no time. So "partition by time" means "partition by file", and a temporal validation cut inside train is only possible if sample_id is chronological, which is undocumented. Ask on Friday; until then treat sample-id order as the proxy and record that assumption in the protocol. This also changes what the rulebook can enforce — see §3.
Store raw ids, build vocabularies later. The frequency threshold (torch-rechub drops ids seen fewer than ten times) is a feature-engineering choice a hypothesis may want to change. The cache keeps every id; vocabulary building is a candidate-side step, fitted on train only.
Keep the history fields as list columns. Parquet handles nested lists natively; a list<struct<id, weight>> column costs little and is where sequence features come from.
Do not load 84M rows into pandas. Stream with pyarrow or polars in row groups; 84M × 31 int32 columns is roughly ten gigabytes before the lists. Partition the parquet so a screening subsample is a file selection, not a scan.
Subsample the training rows, never the evaluation rows. Train has about 9K conversions in 1.6M clicks. A 5% screen leaves ~450 conversions and the CVR AUC on it is noise — this is the problem the synthetic fixture surfaced. The fix is arithmetic: screening trains on a fraction but always evaluates on the full search-validation set, because training is the expensive part and evaluation is not. Keep all conversion-positive rows in the training subsample if the base rate must be preserved for the loss; AUC itself is rank-based and does not care about the base rate.
The ingest hash goes into the protocol. If someone re-ingests with a different join, the hash changes and old runs stop pooling — which is what you want.
3 · Rulebook
Theirs
Nothing. The organisers never see our checks.
Ours
All of it, and it is optional — which is why it is built last.
Judges read
Autonomy: a rule_trip count is countable evidence the agent policed itself without a human.
Do we need it? — the straight answer
Not as a module. You are right that the protocol does most of the work. What the rulebook contains is still needed, but it splits cleanly into three homes that already exist:

The capability rules (no holdout path, no split API, no protocol file in the candidate's reach) are properties of how runner.py launches the child process. They are ten lines of environment and mount setup, not a rule engine.
The post-checks (evaluation row count matches the protocol, metric computed on the declared population, no single feature with AUC > 0.9, subsample positive counts in tolerance) are the leak audit in measure.py. Four functions, each returning pass / fail / warn, each emitting a rule_trip event on fail.
The priors (embedding 8–16, one epoch, feature work beats architecture) are the seed of the hypothesis bank in agents/researcher.py. They were never rules.
And on timing: your instinct to add it late is right — the thresholds for the post-checks (what counts as an implausible single-feature AUC, what tolerance on positive counts) can only be set after you have watched a real Ali-CCP run; before that you would be guessing. So: keep the rule_trip event type (the Reliability tab counts it and it is a cheap Autonomy-criterion story), plan the four checks for step 10 of the build order, drop rulebook.py and the "rulebook" tab unless the product spec needs a place to display the checks. What you lose is a name, not a defence. The rest of this section is kept for the reasoning behind each check.

What's decided
Two collections, never merged: rules are executable checks that fail; priors are starting guesses the agent should overturn. A rule has an id, a plain statement, a severity and a stage.

How this is normally done
Nobody in the agent literature does this well, which is part of why it differentiates. The closest analogues are Kaggle's leakage folklore (out-of-fold everything, adversarial validation) and software linters. The useful framing is a ladder of enforcement strength:

Capability — the forbidden thing is unreachable. The candidate process has no path to the holdout or hidden test because they are not mounted. The candidate receives train and search-validation already split and has no split API to call. Strongest, and free.
Post-check — the harness inspects the result. Row count of the evaluation set equals the protocol's; metric computed on the declared population; subsample positive counts within tolerance; no feature with a single-feature AUC above a threshold.
Static check — grep the diff for train_test_split( without a time key, for .groupby(...).transform("mean") over the label column. Weakest; useful as a warn.
Prefer the top of the ladder wherever possible. A rule that lives as a prompt instruction is not on the ladder at all.

Nuances
Two of the draft rules cannot execute on Ali-CCP. "Time-ordered data is never split randomly" and "per-group statistics use only earlier rows" both need a time column that does not exist. Rewrite them: the split rule becomes a capability (the harness owns the split; there is no candidate-side split), and the statistics rule becomes "label-derived group statistics are computed out-of-fold or on train only; the row's own label never contributes" — which is checkable by re-computing one feature on a sample and comparing.
Rules must be domain-blind enough to run on the synthetic benchmark. If a rule only works on Ali-CCP it is untestable until Friday.
Priors worth writing down now, all from published CTR benchmarking: embedding dimension 8–16 is where every architecture on Ali-CCP sits; one epoch — deep CTR models on sparse id features usually get worse at epoch two (the "one-epoch phenomenon", Zhang et al. CIKM 2022), so the agent should not assume more epochs help; Adam at 1e-3 with batch 4–8K is a safe start; architecture changes are worth ~0.002 AUC on Ali-CCP, feature work is worth 0.01–0.03. That last prior is the one that should shape the initial queue.
Keep solutions out. "Always use out-of-fold target encoding" is a solution, not a rule. It belongs in the hypothesis bank with an expected gain attached.
4 · Event log
Theirs
Nothing touches it.
Ours
The schema, the writer, the file.
Judges read
Presentation (the app is a projection of it), Autonomy (the intervention count is a count over it), Cost (token and GPU sums over it). Three of five criteria are read off this file.
What's decided
One append-only JSONL file per run, flushed on write, every entry stamped with protocol hash, cost, worker id, a one-line summary, a diff path where relevant. Scores as lists. Node ids from one allocator. Profile embedded in the first event.

How this is normally done
This is the event-sourcing pattern from backend engineering: the log is the truth, everything else is a projection over it. Weights & Biases and MLflow do run-level metric logging but have no notion of a search tree, which is why they are not a fit. JSON Lines is the standard container: one object per line, no trailing commas to corrupt, streamable, tail -f-able.

{"seq": 412, "t": "2026-08-29T14:03:11Z", "run": "r-0007", "protocol_hash": "9f1c…",
 "type": "verdict", "node": 18, "parent": 11, "worker": "w1",
 "state": "inconclusive", "metric": "cvr_auc",
 "scores": [0.6531], "seeds": [1], "band": [0.6518, 0.6554],
 "cost": {"gpu_s": 10320, "tokens_in": 0, "tokens_out": 0, "slice": "training"},
 "summary": "node 18 inconclusive: +0.0009 cvr_auc, inside band, requeued at p=0.3"}
Nuances
One writer process. Several workers appending to the same file can interleave partial lines under load. Route every event through a queue to a single writer; that same process is the node-id allocator, so both problems disappear together.
flush() is not fsync(). Flush pushes the line to the OS so the watcher sees it; fsync pushes it to disk so a power loss keeps it. Flush every line; fsync on verdicts and promotions only.
Heartbeats go in a sidecar. Three workers at 30-second intervals over 24 hours is ~8,600 lines of nothing. Write them to heartbeat.jsonl so events.jsonl stays the readable artefact and the Dashboard reads both.
Enumerate event types and version the schema. A fixed vocabulary — run_started, node_created, state_changed, heartbeat, measurement, verdict, failure, recovery, rule_trip, research_source, cache_lookup, hypothesis_queued, queue_reordered, submission_written, intervention, run_ended — and a schema_version on every line, because the app team will start building against version 1 on Tuesday and something will change by Thursday.
Monotonic sequence numbers, not just timestamps. Two events in the same millisecond need an order.
Use git for the candidate workspace. Each node is a commit on a per-run branch; the diff path is patches/node-018.diff generated from git diff parent..node. You get diffs, snapshots and rollback for free.
Store seeds beside scores, as parallel lists. A score without its seed cannot be paired later.
What events.py actually is
About sixty lines, and the only code allowed to open events.jsonl for writing. Every other module calls one function, events.emit({...}), which drops the dict on an in-memory queue and returns immediately. One background thread drains the queue: it stamps seq, the timestamp and the protocol hash, writes the line, flushes. Because there is one writer, lines can never interleave when three workers report at once. The same object hands out node ids (events.new_node(parent)) for the same reason — one counter, no duplicates. Heartbeats go through the same queue to the sidecar file. That is the whole module; it is boring on purpose, because everything else trusts it.

# harness/events.py — the entire public surface
class EventLog:
    def __init__(self, run_dir, protocol_hash): ...
    def emit(self, type: str, **fields) -> int:      # returns seq
    def new_node(self, parent: int | None) -> int:   # unique node id
    def heartbeat(self, worker: str, **fields): ...  # goes to heartbeat.jsonl
    def close(self): ...                             # drains queue, fsyncs
How the log reaches the frontend
The harness never talks to the browser. It appends lines to a file and forgets. A separate, tiny web process (app/server.py, FastAPI or anything) owns the read side: it opens the file, replays every line whose seq is above what the client last saw, then keeps the connection open and pushes each new line as it lands. That is Server-Sent Events — a plain HTTP response that never ends, one data: line per event, which the browser reads with the built-in EventSource object. No WebSocket library, no message broker.

# app/server.py  (the whole read side, in outline)
@app.get("/runs/{run_id}/events")
async def events(run_id: str, since: int = 0):
    async def gen():
        path = RUNS / run_id / "events.jsonl"
        with open(path) as f:
            for line in f:                       # 1. replay history
                ev = json.loads(line)
                if ev["seq"] > since:
                    yield f"data: {line}\n\n"
            while True:                          # 2. then tail
                line = f.readline()
                if line: yield f"data: {line}\n\n"
                else:    await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")

// browser
const es = new EventSource(`/runs/${id}/events?since=${lastSeq}`);
es.onmessage = e => { const ev = JSON.parse(e.data); state = reduce(state, ev); lastSeq = ev.seq; };
Three consequences that make the app simple:

The frontend holds no state of its own. Every tab is reduce(events): the Run tree is the fold of node_created / state_changed; the Hypotheses tab is the fold of hypothesis_queued / queue_reordered; Audit → Cost is a sum over cost fields. Reload the page, replay from seq 0, same picture.
Reconnect is free. The client remembers lastSeq; on drop it reconnects with ?since=lastSeq and misses nothing. Monotonic sequence numbers (above) are what make this work.
Heartbeats use the same endpoint shape on heartbeat.jsonl, but the client only keeps the latest per worker, so "now running" is a lookup, not a list.
If SSE feels like one thing too many for the hackathon, the fallback is the same endpoint without streaming — return the lines after since and have the browser poll every two seconds. Same reducer, same contract; only the transport changes. Start there if the app team is short on time.

5 · Runner
Theirs
The compute budget (TBD) and the expectation that the run is unattended.
Ours
Process isolation, the derived timeout, failure classes and their recoveries, the device.
Judges read
Autonomy (recovers without a human) and Technical (never ends without a valid submission).
What the runner is — and is not
The runner does no training and no tuning. It is a process launcher: given a node (a git commit of the candidate script, a seed, a rung, a device), it starts python train.py as a child process, watches it, kills it at the deadline, and reads back the result.json the child wrote. The training loop lives in the candidate script the coder edits; the "auto" part lives in tree.py deciding what to run next. Think of the runner as the thing that makes a badly-written script fail safely rather than take the whole harness down with it.

What's decided
Separate process per attempt, hard timeout, result read from a file the candidate wrote, failures classified into named classes, recovery per class, heartbeat every ~30 seconds.

How this is normally done
AIDE and MLE-bench both run candidates in a subprocess with a timeout and scrape stdout; the two dominant failure modes MLE-bench reports are "never produced a valid submission" and "never estimated how long it would take". The improvement over that baseline is a contract between harness and candidate: the harness supplies a small library the candidate imports, and the candidate must call report.progress(step, total), report.result(metrics) and checkpoint.save(). Anything that does not honour the contract is a failure class of its own.

Nuances
Classify by exit code and stderr together. CUDA out-of-memory raises a Python exception with "CUDA out of memory" in the trace; host out-of-memory is the kernel killing the process with exit 137 and no trace at all. They need different recoveries (halve batch vs. halve data loader workers).
Diverged training must be self-reported. The harness cannot see a NaN loss from outside; report.progress carries the current loss and the harness kills on NaN or on loss exceeding its initial value by a factor.
The timeout is derived, not fixed. Time per row on the screening run, times full row count, times epochs, times a safety factor. A fixed 3-hour cap either kills good runs or wastes hours on bad ones.
Retry counts toward the node's cost and the retry is a new event with attempt: 2, not an edit of the first.
Concurrency means CUDA_VISIBLE_DEVICES per worker, and on one GPU it means one full-data worker. Screens can run on CPU or share the card; two full-data trainings on one 40 GB card will OOM each other and you will be debugging that at 4 a.m.
Resume-from-checkpoint only works if the candidate template checkpoints. Put it in the template, not the prompt.
The tuner, the runner and the GPU — who does what
There is no separate "thing that runs on the GPU and tunes". Three pieces, each dumb on its own:

agents/tuner.py is an Optuna study. It picks knob values (learning rate, embedding size, batch) and asks for a score. It never trains anything.
Each trial is just another candidate run. The tuner writes the knob values into a copy of the current template, and hands it to runner.py on the screen rung. Fifty trials = fifty short subprocesses, in sequence or a few at a time.
The GPU is used by the candidate subprocess, because it is the only thing that calls torch. The tuner and runner are pure Python on the host.
So "how do we route to the A100" has two answers, and you should take the first:

# Answer 1 (default): the whole harness runs on the A100 box.
#   laptop → ssh -L 8000:localhost:8000 gpu-box → browser at localhost:8000
#   Nothing is "routed"; the child process is local to the GPU.

# Answer 2 (only if the harness MUST stay on the laptop): a Backend seam in runner.py.
class Backend(Protocol):
    def run(self, workspace: Path, cmd: list[str], env: dict, timeout: int) -> RunResult: ...

class LocalBackend:   # subprocess.Popen, what everything above describes
class SSHBackend:     # rsync workspace → gpu:/scratch/<node>; ssh gpu "cd … && python train.py";
                      # rsync result.json + checkpoint back; ~80 lines, adds latency and two failure classes
Answer 2 is the "abstracted thing" you were picturing. It exists as a seam so the runner does not care where the child lives, but it is a week-two luxury; build it only when you have a GPU box and a reason not to run everything there.

Optuna, semi-deep: what tuner.py is actually made of
Optuna is a hyperparameter optimiser and nothing more. You write an objective function that asks trial.suggest_float / suggest_int / suggest_categorical for values, trains, and returns one number; a sampler picks the next values from the history; a pruner can kill a trial early from intermediate scores. One call of the objective is a trial; the set of trials is a study. Versions as of 26 Aug 2026: v4.9.0 (1 Jun 2026) is the latest stable; v5.0.0-rc1 (3 Aug 2026) is a pre-release that changes the defaults noted below — pin 4.9 and set the v5 defaults by hand. Every claim here is traced to the docs, the GitHub release notes or the source in ~/Downloads/optuna-deep-dive-research.md.

Piece	What it does, plain	What the docs say that matters here
Search space	"Define-by-run": the space is whatever suggest_* calls actually execute, so conditional knobs (if model == "deepfm": suggest_int("cross_layers", …)) are legal.	"The number of necessary trials increases exponentially when you increase the number of parameters" — tune 3–6 knobs, not 15.
TPESampler	Tree-structured Parzen Estimator: split past trials into a "good" set and a "bad" set, fit a density to each, propose the point most like the good ones and least like the bad ones.	The first n_startup_trials = 10 trials are plain random. The docs' sampler table recommends TPE at 100–1000 trials. multivariate=True models the knobs jointly; constant_liar=True stops parallel workers proposing the same point. Both become defaults in v5.
GPSampler	Gaussian-process Bayesian optimisation with a learned noise term (deterministic_objective=False by default).	What OptunaHub's AutoSampler picks below 250 trials for purely numerical spaces. Needs scipy and torch. This is the sampler for 10–50 trials.
CMA-ES / QMC / Random / Grid / BruteForce	Evolution strategy for 1000+ trials; low-discrepancy sequences; the baselines.	CMA-ES has no categorical support; QMC Sobol wants a power-of-two trial count.
Pruners	The candidate calls trial.report(value, step) then trial.should_prune(); Median, SuccessiveHalving, Hyperband and Patient compare trials at the same step.	MedianPruner does nothing until 5 trials complete; Hyperband with max_resource="auto" prunes nothing until one trial finishes. For one-epoch CTR models step must be a sub-epoch checkpoint or there is nothing to compare.
WilcoxonPruner (v3.6)	The one noise-aware piece: a paired signed-rank test of this trial against the best trial across "instances" (seeds or folds); stops the trial once it is statistically worse at p_threshold = 0.1.	Report each seed as an instance (trial.report(auc_seed_i, step=i)) and return the mean — the Optuna-native form of paired seeds.
Warm start	study.enqueue_trial(params) runs a known config first; study.add_trial(…) injects results you already measured; trial.set_user_attr stores seed, checkpoint path, node id as JSON.	Enqueue the incumbent's knobs so trial 1 is the baseline, and add every earlier node's result so the sampler learns from them for free.
Parallel	Several processes share one storage; each runs the same script with load_if_exists=True.	n_jobs is thread-based and GIL-bound. "We would never recommend SQLite3 for parallel optimization" — use JournalStorage(JournalFileBackend) on one host, Postgres across hosts. File locks break on NFS.
Ask-and-tell	trial = study.ask(); … ; study.tell(trial, value) — the study is driven from outside instead of through study.optimize.	This is the shape tree.py needs: the tuner asks, the runner trains, the tuner tells. An Optuna MCP server (v4.4) exists so an LLM can drive studies; you do not need it.
Terminator (v3.2)	Stops a study when the GP's regret upper bound falls below the cross-validation error — "more search is pointless given the noise", formalised (Makarova et al. 2022).	Needs ≥ 20 completed trials and per-trial CV scores; deprecated in 4.9, moving to OptunaHub. Use it once, on the long baseline-tuning study, not on 50 short ones.
Multi-objective	directions=["maximize", "minimize"] → a Pareto front in study.best_trials.	best_value raises; pruners are single-objective only. Relevant if log loss becomes a co-primary (§6).
Ecosystem	optuna-dashboard 0.20 live plots; optuna-integration callbacks; OptunaHub registry (optunahub.load_module("samplers/auto_sampler")).	The dashboard is a second UI you do not need — the trial table goes on the node and the app draws it.
What Optuna does not do — and why the tuner sits under the ladder, not beside it
No seed averaging, no de-biased best, no interval. study.best_value is the raw maximum over noisy trials, so it carries the full winner's-curse bias of §6: with σ = 0.015 the best of 50 trials looks ~0.03 better than it is. Bischl's advice to return the surrogate's predicted best rather than the observed best is not implemented. Re-run best_params on fresh paired seeds outside Optuna — that is exactly "the shortlist climbs the ladder".
No idea generation. The 50 hypotheses are not a categorical knob. A categorical with 50 arms and one trial each is random search with extra steps; an idea's continuous knobs (learning rate, embedding size, dropout, batch) are what a study is for.
Trial count is the binding constraint. Under 10 runs: do not create a study; enqueue 2–3 hand-picked configs. 10–50 runs, ≤ 6 numeric knobs: GPSampler(n_startup_trials=5). 50–300 runs with categoricals: TPESampler(multivariate=True, constant_liar=True). The baseline gets the one long study (50–100+ trials) so the zero point is honest (Rendle).
# harness/agents/tuner.py — the whole file is ~40 lines around this loop
storage = JournalStorage(JournalFileBackend(f"runs/{run_id}/optuna.log"))
study = optuna.create_study(direction="maximize", sampler=GPSampler(n_startup_trials=5),
                            storage=storage, study_name=node.id, load_if_exists=True)
study.enqueue_trial(incumbent.knobs)                    # trial 1 = the baseline's own knobs
for _ in range(budget):
    trial = study.ask()
    knobs = {"lr":      trial.suggest_float("lr", 1e-4, 1e-2, log=True),
             "emb":     trial.suggest_int("emb", 4, 32, step=4),
             "dropout": trial.suggest_float("dropout", 0.0, 0.5)}
    trial.set_user_attr("seed", protocol.screen_seed)
    result = runner.run(node.with_knobs(knobs), rung="screen", seed=protocol.screen_seed)
    if result.ok: study.tell(trial, result.metrics["cvr_auc"])
    else:         study.tell(trial, state=TrialState.FAIL)
shortlist = sorted((t for t in study.trials if t.value is not None),
                   key=lambda t: -t.value)[:3]           # → child hypotheses, NOT promotions
Every trial is a node-level event (node_created with parent = node.id, kind trial), so the Cost tab's "tuning" slice and the sweep's trial table both fall out of the log with nothing extra built.

Where training runs — and yes, CPU is fine for most of it
The CUDA lines above are about failure classification, not a requirement. The routing question has a short answer: there is no routing. The runner starts the child on the same machine it is running on, and tells it which device to use through one environment variable. The candidate template reads it and nothing else in the system cares.

# protocols/aliccp.yaml — run block, NOT hashed
run:
  device: cpu            # cpu | cuda | mps
  workers: 1

# harness/runner.py
env = {**os.environ, "DEVICE": run.device, "SEED": str(seed),
       "TRAIN": paths.train, "VALID": paths.search_validation}
if run.device == "cuda": env["CUDA_VISIBLE_DEVICES"] = str(worker.gpu_index)

# harness/candidate/template.py
device = torch.device(os.environ.get("DEVICE", "cpu"))
Whether CPU is enough depends on the rung, because the models here are small — DeepFM / MLP over sparse ids with an embedding size of 8–16, the same class NISE uses. Rough figures, to be replaced by what the screening run measures (that is what the derived timeout is for):

Rung	Rows trained	Laptop CPU (8-core)	One T4 / A100	Verdict
Synthetic benchmark	~1M	seconds to a minute	same	CPU, always
Screen (5% subsample, full eval)	~2M	a few minutes per epoch	under a minute	CPU is fine; this is most of the run's node count
Full run, one seed	~42M	tens of minutes to ~2 h per epoch, loader-bound	5–10 min	CPU possible with 1–2 epochs; GPU if you have one
Replication, 3 seeds paired	3 × 42M	half a day	~30 min	this is where a GPU pays for itself
Three practical notes:

Memory, not compute, is the first wall on a laptop. 42M rows × 31 int32 columns is ~5 GB before the history lists; with 16 GB of RAM it fits, with 8 GB it does not. The parquet partitioning in §2 is what lets a screen load 5% without touching the rest.
Apple's MPS backend is not worth the trouble here. Sparse embedding backward has gaps on MPS; the M-series CPU with a decent loader is simpler and the numbers match CUDA runs (determinism is off in the protocol anyway).
If you do rent or borrow a GPU, run the whole harness there, not just training. The harness is one process tree; splitting "runner on the GPU box, tree on the laptop" means building a job queue and you do not have the week for it. The laptop then only runs the browser, pointed at app/server.py on the GPU box through an SSH port-forward. A Kaggle or Colab GPU session works for a single full run or a replication batch; a rented card (the Nebius credits, if still live) works for the unattended 24 h run.
The honest plan for the hackathon week: develop and demo everything on CPU against the synthetic task and Ali-CCP screens; spend GPU hours only on iteration 0 (baseline × 5 seeds), the top-rung replications, and the final unattended run.

6 · Measurement
Theirs
The metric definitions and their populations (CTR AUC over all impressions, CVR AUC over clicked rows) and the ε / N convergence rule.
Ours
The noise band, the ladder, the promotion bar, the holdout, the leak audit — everything that decides whether a number is believed.
Judges read
Technical: the hidden-test delta is only real if this layer is right, and this is where a judge who knows statistics will probe.
What's decided
Noise calibration from repeated baseline runs → promotion bar; a three-rung ladder (screen, one full run, several seeds); inconclusive is a state, not a rejection; a leak audit that fires on implausible gains.

How this is normally done
In the agent literature it mostly is not — which is the differentiation. In evaluation methodology it is, and the research pass below traced the rules to their sources. Two separate noise sources matter here and they are often confused, and a third failure mode is not noise at all:

Training noise — same data, different seed, different model. On Ali-CCP CVR this is ±0.012–0.017 AUC, as large as most published method gaps.
Evaluation noise — same model, different validation sample. With ~9K conversion positives the 95% interval on CVR AUC is about ±0.006 (Hanley–McNeil); small next to seed noise, and it mostly cancels when both models are scored on the same rows.
Validation overfitting — not noise: after fifty candidates have been picked because they scored well on search-validation, the best one's score is biased upward. The best of fifty null candidates looks about 2.25 standard deviations better than baseline by chance alone — roughly +0.03 AUC at one paired seed.
Research pass: how you tell real from noise from overfitting
You asked for the papers, for an answer to "what is our eval for a good run, beyond beating the baseline", and then — rightly — where the numbers came from and what is contested. Four write-ups now sit next to each other in ~/Downloads: beating-nise-measurement-research.md (the classics, 25 Aug), real-vs-noise-vs-overfit-2026-research.md (the 2021–2026 literature and the numeric ladder), measurement-ladder-contested-points-research.md (each rung's number: published, derived or convention, and who disagrees) and optuna-deep-dive-research.md (§5). This is the part that becomes code, revised 26 Aug where the newer literature overruled the first version.

Where the numbers came from — straight answer
The ladder is not from a paper. Its shape (screen → replicate → confirm; reject early, promote late) is the racing pattern from algorithm configuration — SMAC's intensifier (Hutter et al. 2011) and irace (López-Ibáñez et al. 2016, which waits five instances before eliminating anything). Its mechanisms are published: paired seeds and the P(A>B) ≥ 0.75 rule (Bouthillier 2021), Benjamini–Hochberg (1995), the Ladder (Blum & Hardt 2015), a fixed checkpoint rule (Zhang 2022). Its σ is ESCM2's Table 2. Every number that glues those together — promote at 1σ, reject at −0.01, mean Δ ≥ 0.010, q = 0.10, η = 0.005, a 0.01 gap, ten holdout queries, three then five seeds, 75 runs — is arithmetic on σ or a convention I chose. None is a published recommendation, and two were wrong: three seeds cannot carry a test, and "detectable at 80% power" used a normal approximation that overstated power. Both are corrected below.

The structural fact the ladder rests on (derived, not in any paper, but it follows from them): seed noise is a property of the trained model, so it moves that model's validation AUC and holdout AUC together. Seed luck cannot create a validation–holdout gap. That splits the three verdicts cleanly:

Noise is decided by paired seeds — does the per-seed Δ hold up when you repeat?
Overfit to validation is decided by the candidate's val–holdout gap minus the baseline's (a difference-in-differences), by checkpoint sensitivity, and by whether the other person can reproduce the gain from a short description without touching validation.
Distribution shift (the holdout is simply later or harder) is a shared drop: baseline and candidate both fall by about the same amount, and the candidate is judged on Δ alone (Recht 2019, Taori 2020).
Failure mode	Size on Ali-CCP CVR	The test that catches it	Source
Training-seed noise	σ = 0.011–0.017 AUC over 10 seeds (ESCM2 Table 2); their own paired t-test could not star a +0.007 gain. Runs with an identical fixed seed still differ (Pham 2020: up to 2.9 accuracy points; Zhuang 2022: implementation-only spread exceeds seed-only spread on a V100), and CTR embedding gradients use exactly the atomic scatter ops that are nondeterministic — so "same seed" is only partly paired, and ρ must be measured.	Paired seeds; Student-t on the per-seed Δ (not z, not bootstrap below ~10 seeds — Bowyer 2025, Jordan 2020, Colas 2019); a Beta posterior on the paired-win count against γ = 0.75.	ESCM2, Bouthillier 2021, Pham 2020, Zhuang 2022, Bowyer 2025, Colas 2019
Evaluation-sample noise	±0.006 at ~9K positives; negatives do not matter. At 1.5M rows a row-level DeLong test comes out "significant" for differences far below seed noise — the seed-level test is the binding one (Ihemelandu & Ekstrand 2023).	DeLong's paired test or a bootstrap of the difference on shared resamples; report the effect size, not the star.	DeLong 1988, Ihemelandu & Ekstrand 2023
Validation overfitting from search	Best of 50 nulls ≈ +2.25 SD by chance. Now measured in agents: AIRA-dojo (20 seeds per task) shows validation keeps climbing while test plateaus; picking the final node by test instead of validation would add 9–16 medal points; MLE-bench dropped Kaggle's public leaderboard for this reason. In HPO, Schneider–Bischl–Feurer 2025: ~60% of runs show no overtuning, ~10% severe.	BH across candidates at the replication rung; a never-searched holdout that makes the final pick among the top-3 validation nodes; the difference-in-differences gap; one-bit Ladder reporting (Bertran–Roth–Wu 2026 show it loses nothing); a reproduce-from-≤64-tokens test.	AIRA-dojo 2025, MLE-bench, Schneider 2025, Bertran 2026, Blum & Hardt 2015
Stopping luck	Deep CTR models collapse at the start of epoch 2 (Zhang 2022) — but MEDA (Kuaishou 2024), Pinterest 2025 and Li & Lyu 2025 make multi-epoch training beat one-epoch by +0.7 to +5 AUC points. A fixed "best of epoch 1" rule would disqualify that whole family of candidates.	Best-validation checkpoint at a fixed evaluation cadence, declared per candidate; the baseline is re-run under the candidate's rule if the rule changes; a checkpoint-sensitivity check on saved checkpoints.	Zhang 2022, MEDA 2024, Pinterest 2025, Li & Lyu 2025
The arithmetic, corrected (σ = 0.015; Student-t, not z)
Paired seeds k	SD of Δ (ρ = 0.5 / 0.8)	SE of mean Δ	Smallest mean Δ you can call real, α = 0.05	Same at Colas' α = 0.01	Wins needed (P(A>B) ≥ 0.75 on a Beta posterior)
1 (screen)	0.015 / 0.0095	—	never	never	—
3	0.015 / 0.0095	0.0087 / 0.0055	0.025 / 0.016	0.060 / 0.038	3/3 is "promising" only (null p = 0.125; posterior 0.68)
5	0.015 / 0.0095	0.0067 / 0.0042	0.014 / 0.009	0.025 / 0.016	5/5 passes (null 0.031; posterior 0.82); 4/5 does not (0.47)
10	0.015 / 0.0095	0.0047 / 0.0030	0.0087 / 0.0055	0.013 / 0.0085	≥ 9/10 (null 0.011; posterior 0.80); bootstrap and IQM become usable here (Agarwal 2021)
SD of Δ = σ·√(2(1−ρ)); SE = SD/√k; threshold = tk−1·SE with one-sided t = 2.92 / 2.13 / 1.83 at k = 3 / 5 / 10 (6.96 / 3.75 / 2.82 at α = 0.01). The first version of this table used z = 1.645 + 0.84 and said 0.022 was detectable at k = 3; the t-based figure is 0.035. The lines to remember: one seed sees nothing under ~0.03; three seeds cannot certify anything; five paired seeds certify ≈ 0.014 (ρ = 0.5) or ≈ 0.009 (ρ = 0.8). That is about a quarter of the entire ESMM → ESCM2 literature gain on this dataset (0.607 → 0.616), and the write-up should say so before a judge does.

The ladder, with numbers — v2
Same four rungs, same ~75 runs, three changes forced by the literature: the screen is reject-only, replication needs five seeds to certify, and the holdout decides the final pick. Thresholds are stated at ρ = 0.5 / 0.8; rung 0 tells you which column you are in. The screen still runs on the 5% training subsample of §2, with its thresholds set from the screen's own σ.

Calibrate (7 runs, once). Baseline on 5 seeds → σ (5 seeds pin σ only to a factor of [0.6×, 2.9×], so treat it as a band, not a number). Two more runs with an identical fixed seed → σfix, the nondeterminism floor; if σfix > 0.5σ, pairing will not reach ρ = 0.8 and the ρ = 0.5 column applies. Record per seed: validation AUC and holdout AUC (the baseline's own gap and calibration ratio are the reference for rung 3), log loss (its seed σ is often far lower than AUC's — Madaan 2024 — so it is a cheap co-screen), and the checkpoint rule: best-validation checkpoint at a fixed cadence, evaluated every N minibatches, not "epoch 1". If σ > 0.02, fix training instability before anything else.
Screen (~45 runs, one paired seed each) — reject-only. Shared seed s₀. Δ < −0.01 → rejected; Δ ≥ 1 SDΔ (0.015 / 0.0095) → goes to replication; between → inconclusive, not tested. Honest numbers at this bar: about 8 of 50 null ideas get through, and only 37% of true +0.010 ideas do. That is what one seed buys; SMAC and irace also reject on one paired loss and never promote on one win. Do not rank the screen: the best of 45 nulls is ≈ +0.033 / +0.021 by chance. The holdout is not touched.
Replicate (~12 runs: two more seeds for the top 5–6). k = 3: 3/3 wins and mean Δ ≥ 0.025 / 0.016 → provisional pass; 3/3 wins with mean Δ between 0.010 and that bar → buy two more seeds. k = 5: 5/5 wins, or 4/5 with mean Δ ≥ 0.014 / 0.009 → pass; use 0.025 / 0.016 if you adopt Colas' α = 0.01. Benjamini–Hochberg at q = 0.10 across the candidates at this rung (defensible: Benjamini–Yekutieli 2001 cover many-treatments-vs-one-control). From the saved checkpoints, no new training: if Δ flips sign or moves by more than 2 SDΔ across 0.9 / 1.0 / 1.1 epochs, the node is "overfit to validation" whatever its mean. No bootstrap intervals at k ≤ 5.
Confirm on the holdout (~10 runs: 5 paired seeds, at most 2 finalists, reusing rung-2 seeds). DiD = (val − holdout)candidate − (val − holdout)baseline, SD ≈ 0.0063 at 9K positives. DiD > 0.013 → "overfit to validation"; 0.007–0.013 → consistent with winner's curse alone, one more seed; ≤ 0.007 and Δholdout ≥ Δval − 0.010 → promoted. Both models drop together → distribution shift, judge Δ only. Reporting goes through a Ladder: a finalist's holdout AUC becomes the new "best reported" only if it beats the old one by η = 0.005 (a convention — Blum & Hardt's theory gives η = 0.02–0.11 here, useless; their deployed variant is a paired t at roughly the 0.15 level). Before calling it real, the description test: the other person reproduces the gain from ≤ 64 tokens on a fresh seed without validation access. The final submission is picked on the holdout among the top-3 validation nodes, never by the single best validation score (AIRA-dojo: submitting the top-3 is worth ~10%).
What inconclusive means, precisely: the data are consistent with zero effect and with an effect the size of the threshold. It is not a weak positive. Never stack two inconclusive changes and count the pair as a win — re-measure the combination at rung 2. Effects below ≈ 0.014 (ρ = 0.5) cannot be certified on a 75-run budget at all; they are filed as "not refuted" and accumulate for one combined re-test.

Contested — say these in the write-up before a judge does
σ = 0.015 is not a fact about Ali-CCP; it is a fact about one pipeline. ESMM's CVR AUC on the same public data is 0.607 ± 0.013 (ESCM2, 10 seeds), 0.629 ± 0.006 (AITM, 5 seeds), 0.670 with no std (EVI, AAAI 2025); PLE reaches ± 0.0013 in AITM. Low-frequency ID filtering, learning rate, embedding size and the checkpoint rule move the mean by 0.06 and the std by 10×. Rung 0 is the only honest source of σ, and every threshold above scales with it.
Three seeds cannot carry a test — a sign test with 3/3 has p = 0.125; Bouthillier's own sample-size formula for the γ = 0.75 rule gives N ≥ 17 (β = 0.2) to 29 (β = 0.05). Rung 2 at k = 3 promises "promising", not "real".
AUC alone is contested for CVR. Facebook (He 2014) reports normalised entropy plus calibration because AUC ignores calibration; Google's auction needs calibrated probabilities; ESCM2 could not star its own AUC gain, only KS/F1/Recall. Log loss and PCOC (predicted-over-observed conversion ratio) as co-primary guards; a candidate that wins AUC and loses calibration is inconclusive.
The ten-query holdout cap is theatre in theory (Ladder error grows as log k; Roelofs: i.i.d. holdouts survive thousands of queries) and discipline in practice. The step rule and a valid split are what actually protect it.
No LLM-agent paper has a per-candidate seed policy. AIDE and ML-Master evaluate each node once and take the argmax; MLE-bench's 3 seeds are agent-level. The formal ancestor of this ladder is SMAC intensification, and saying that is more credible than claiming novelty.
Good run vs bad run: the scorecard
You are right that "beat the baseline in the protocol" cannot be the run-level eval, because the baseline is the zero point, not the judge. A run is judged on five numbers, all of which are projections over the log and all of which the Audit tab can show:

Baseline reproduced — iteration 0's five seeds land inside the published spread for the matching preprocessing (ESCM2's 0.011–0.017 or AITM's 0.001–0.006; the two pipelines differ by 0.02 in mean AUC). If not, nothing after it counts.
Promotions that survived the holdout / promotions that reached it. This is the honest hit rate of the search.
Validation − holdout gap of the final incumbent, next to the baseline's gap. The difference between them is how much the search overfit.
Prediction accuracy — the hidden-test delta the run wrote down before scoring versus the delta the organisers report. A run that predicts +0.008 ± 0.006 and gets +0.007 is a good run even if the number is small; a run that predicts +0.03 and gets +0.005 is a bad run even though it "beat the baseline".
False-promotion rate on the synthetic benchmark — the planted zero-effect feature (§10) must not be promoted, the planted +0.01 feature must be, the planted leak must trip the audit. This is the only one you can compute before any GPU time.
Two sources that change how you read all of this: Rendle et al. show the dominant evaluation error in recsys is an under-tuned baseline, not statistics — significance "measures the variance within one setup" (Rendle 2019) — so the tuner runs on the baseline as hard as on any candidate; and BARS notes 0.001 AUC counts as practically significant on Criteo with 1.1M test positives (Zhu 2021) — on Ali-CCP CVR with 8K positives and σ = 0.015, it is not resolvable, and the writeup should say so before a judge does.

Nuances
Pair the seeds — and measure how paired they really are. Run the candidate and the incumbent with the same seed set and compare per-seed deltas. The delta's spread is smaller than either score's spread because part of the training noise cancels ("common random numbers" in simulation). But a GPU does not replay a seed exactly — embedding scatter-adds are nondeterministic — so rung 0's two identical-seed runs tell you the floor. If the observed SD of Δ ever exceeds 1.4σ, pairing has failed (ρ ≤ 0) and you are in the unpaired column: double k.
Calibrate on the screen, validate the ratio once. Five full baseline runs is ~15 GPU-hours before the first idea. Measure the noise band on the screening subsample for five seeds, then run the full baseline three times to estimate the ratio between screen noise and full noise. Cheaper, and the ratio itself is a Replication-tab number.
The bar is a multiple of the band, and the multiple is now stated above (+1 SDΔ to leave the screen; 5/5 wins or mean Δ ≥ 0.014 / 0.009 plus BH to be promoted; DiD ≤ 0.007 and η = 0.005 on the holdout). Say the arithmetic in the write-up, and say which numbers are convention — judges who know statistics will ask, and "we chose q = 0.10" is a better answer than a citation that does not say it.
Leak-audit triggers and checks. Trigger on gain above roughly five bands. Checks: any single feature with AUC above 0.9 on its own; train–validation gap widening; adversarial validation (can a classifier tell train rows from validation rows using the new features?); re-run with the new feature ablated. If the gain collapses, mark the idea family down, not just the node.
Promotion requires holdout agreement. Top-rung candidates are also scored on the holdout the agent never saw. A candidate that wins on search-validation and loses on holdout is recorded as such — that is the third replication pair, and it is the one that tells you whether the search has started fitting the public validation.
7 · Run tree & Hypotheses was: Search
Theirs
When the loop ends — their convergence rule, copied exactly.
Ours
What to try next, in what order, and when to give up on a family.
Judges read
Innovation (what the agent chose to target and why) and Autonomy (the tree ran itself).
What's decided
A tree of attempts with parent, state and result; a queue ranked by expected gain over expected cost, reranked after every measurement; families that fail drop wholesale; nodes go terminal after consecutive non-improvements.

How this is normally done
2025. AIDE keeps a solution tree and picks actions by fixed probabilities — its shipped defaults are num_drafts = 5, debug_prob = 0.5, max_debug_depth = 3, steps = 20, greedy improve on the best validation node. ML-Master adds UCT selection with a scoped memory of sibling outcomes (29.3% MLE-bench any-medal with DeepSeek-R1 in 12 h). MLE-STAR is linear, not a tree: an ablation picks the pipeline block that matters most, then four refinement plans target that block (valid-submission rate 78.8% → 95.5%, mostly from checkers). R&D-Agent splits researcher from developer over a DAG of parallel traces, diverse at the root and greedy within a branch.

What 2025–2026 found out about all of them. The one controlled comparison of selection rules (AIRA-dojo, Meta, 20 seeds per task) found that with the same operators, greedy, MCTS and evolutionary search "gain no advantage" over each other; better operators moved the medal rate 39.6% → 45.5% (greedy) → 47.7% (MCTS). FML-bench (May 2026, 324 runs) found Karpathy's plain greedy autoresearch loop (0.192) tied with AI Scientist v2's tree search (0.193); an adaptive policy that runs greedy and forks only on a stall scored best (0.208); token spend and wall-clock did not predict outcome. What took the MLE-bench leaderboard from ~30% to ~63–65% was not a selection rule: memory across branches (ML-Master 2.0 56.4%; MARS reports 63% of the lessons it used came from other branches), asynchronous multi-GPU execution plus a hidden evaluation split (AIRA2: +13 points at 24 h and +18 at 72 h from the evaluation change alone), and stronger base models. Microsoft's Gome (Mar 2026) adds that the tree is a crutch for weak reasoners: with frontier models, directed updates from a good diagnostic beat enumeration.

So the spec's "expected gain over cost, reranked on evidence" has partial precedent and no direct test. AIDE² (Weco 2026, an outer AIDE rewriting the inner one) evolved the greedy rule into "a multi-armed bandit where each draft's subtree acts as an arm" with fork-on-stall (+0.053 on MLE-bench Lite, p = 0.002); MARS multiplies UCT reward by a runtime penalty; ShinkaEvolve runs UCB1 over LLMs; R&D-Agent(Q) uses a bandit between two idea types. Nobody has isolated a gain-per-GPU-hour bandit over idea families. And one warning that decides how to build it: Gupta, Hartford and Liu (EMNLP 2025) found LLM agents "show no sensitivity to experimental feedback" — permuting the outcomes changed nothing — while plain bandits and GP optimisers beat them. The evidence update must be arithmetic on your own log, never the researcher's opinion of what worked. Every system's constants and numbers are in ~/Downloads/mle-agent-search-policies-2026-research.md.

What this means for tree.py — the cheapest design the evidence supports
Greedy on the incumbent by default: keep a change if its paired-seed Δ clears the §6 bar, else revert. This is autoresearch's loop with a noise floor, and FML-bench could not tell it from tree search.
Fork only on stall: four consecutive non-improving improve steps → open two fresh drafts in the two idea families with the highest (mean Δ so far + 1 SD) / mean GPU-minutes, computed from the event log. At most three live branches. This is AIDE²'s subtree-as-arm and FML-bench's adaptive policy, the only rules that beat plain greedy in their own studies.
Actions: draft / debug (depth ≤ 3) / improve / ablate (once per stall, MLE-STAR-style, to find which block is worth changing) / ensemble (last hours only).
Fidelity tiers: tier 0 a static check and a 60 s smoke run (invalid submissions are where AIDE lost most); tier 1 the §2 screen subsample; tier 2 full data, paired seed. After five full runs, compute the screen-vs-full correlation and drop the screen tier if it is under 0.5 (ArchPilot's recalibration, in spirit).
Final pick on the holdout among the top-3 validation nodes, never the single best validation score (AIRA-dojo, AIRA2).
A lessons file: after every full run append diff summary, Δ, family, GPU-minutes; feed the last 30 into the improve prompt (MARS keeps 30). The one ingredient that separates 2026 systems from 2025 ones, and it is a file.
Skip: MCTS constants, island models, LLM value estimates, and any "expected gain" the LLM produces rather than the log. What you can claim: consistent with the strongest controlled evidence. What you cannot: that the bandit itself adds anything — nobody has measured that.
Nuances
A queued hypothesis is not a queued diff. The incumbent changes; a patch written against node 11 will not apply to node 18. Queue the hypothesis (stage, mechanism, expected gain), and have the coder generate the diff against the current best when it is dequeued.
A family is a pipeline stage, not a method — so the list is closed and short. Your worry is right: if "family" meant "method name" the agent could not know the taxonomy, because the field moves. So the tag has two parts. The first is the stage the change touches, and there are only six for any tabular pipeline: data (rows, sampling, cleaning), features (new columns, encodings, vocab thresholds), objective (loss, multi-task weighting, label handling), architecture, training (optimiser, schedule, epochs, regularisation), ensemble (blending, post-processing). That list is fixed in the JSON schema the researcher must fill, and it does not go stale because stages are not methods. The second part is a free-text mechanism slug (target-encoding, escm2-ipw) that the researcher invents; new ones are allowed. Expected gains are updated at the stage level first, mechanism second. This is the same move MLE-STAR makes when it ablates by pipeline block.
Update expected gains at the family level. Tag every hypothesis with a family (feature/target-encoding, loss/multi-task, arch/cross-network). A dead screen lowers the family's expected gain; a promotion raises it. Otherwise "families drop wholesale" has nothing to act on.
Keep a little exploration — as fork-on-stall, not a random fraction. A purely greedy queue converges on the first family that worked; a random ε wastes runs on ideas the log already scored low. Fork into the two best-scoring other families only when the incumbent stalls, so the tree's breadth is earned by evidence and shows up in the Run tree tab as a visible decision.
Dedupe before queueing. The researcher will propose target encoding four times with four names. Family tag plus stage plus a short normalised description is enough of a key.
Sweeps are one node, with the trial table attached, and only the shortlist becomes child nodes.
State vocabulary is the product spec's, verbatim: screening, running, replicating, promoted, inconclusive, rejected, retired, leaked, debugging. The event log's state field takes only those values.
8 · Agents
Theirs
Nothing, unless the brief restricts which LLM providers may be used — check on the 28th.
Ours
Researcher, coder, tuner, brief, cache; which model runs which role.
Judges read
Innovation (a cited mechanism on every hypothesis) and Cost (tokens per node, per slice).
What's decided
A researcher on a strong model proposing one atomic change with mechanism, citation, expected gain and cost; a coder on a cheap model writing diffs from tracebacks; a classical tuner for continuous knobs; a brief composer (the designated cut); a research cache whose second visit is a verification.

How this is normally done
The researcher/developer split is R&D-Agent's; scoped memory (show the coder only what it needs) is ML-Master's; the always-valid-submission discipline is the direct answer to MLE-bench's top failure mode. Using a classical optimiser for hyperparameters is simply what everyone outside the LLM-agent literature already does — Optuna with TPE and a pruner is the default.

Nuances
Structured output, validated, or the hypothesis is rejected unrun. A JSON schema with stage, family, mechanism, citation | "no prior", expected_gain, expected_gpu_h. Rejecting a proposal for missing an expected gain is a rule trip, and it is countable.
Seed the hypothesis bank before the run. Innovation is judged on what the agent chose to target and why. Give the researcher a starting bank drawn from the literature with expected gains attached — feature-side ideas first, because that is where Ali-CCP's headroom is — and let the reranking take over from hour one. An empty bank means the first hours go to tuning that cannot move the number.
Tune on the screen only. The tuner's trials are cheap by construction; a trial on full data costs three hours and defeats the purpose. Its shortlist then climbs the ladder.
Tag every LLM call with node id and slice. Token accounting per node is impossible after the fact; read the usage fields off each response and write them to the log with the call.
Cache key = normalised query + protocol hash. A finding measured under one split is not a finding under another; the hash in the key makes invalidation automatic.
The coder never sees the holdout path, the protocol file, or the rulebook source. Capability, not instruction.
Emit research events as they happen (research_source per paper, cache_lookup with hit/miss and confirmed/contradicted) or the Research tab has nothing to draw.
9 · Audit & outputs was: Outputs
Theirs
The submission format (their example submission), which head is scored, and whether it is predictions or a checkpoint.
Ours
The writer, the read-back check, the registry, the report.
Judges read
Technical (the file that gets scored) and Presentation (the report).
The backend spec's feature 9 splits into two under product-spec naming: Audit (replication, cost, reliability — the three product-spec children, all pure projections over the log) and outputs proper (submission writer, convergence and prediction, run registry, report export).

Audit
Replication was: transfer recorder — three pairs per node: screen vs full, one seed vs several, search-validation vs holdout. Nothing to build beyond reading verdict events; the pairs exist because the ladder ran.
Cost was: cost ledger — four slices: researching, coding, training, tuning. Tokens from API usage fields; GPU-hours as allocated time × device count, not utilisation. A committed reference/published_costs.yaml holds the AIDE and MLE-bench figures for comparison.
Reliability — failures by class, recovery outcome, time to first valid submission, longest unattended stretch, and rule trips as their own category.
Outputs
Nuances
We do not yet know whether we submit predictions or a checkpoint. The brief says "final predictions/checkpoint". If hidden-test features are provided without labels, we write predictions; if not, we ship a checkpoint plus an inference script the organisers run. Build the writer to do both; the read-back check (row count, columns, ranges) applies to the predictions path, and a dry-run inference on search-validation applies to the checkpoint path.
Write the right head. The CVR column must be p(conversion | click), per the protocol's metric entry. A submission that writes p(click and conversion) will score, and score badly, and nothing will explain why.
Convergence uses the organisers' rule exactly — ε and N from the protocol, "improved" measured on search-validation, validation-best checkpoint retained — and the counter is emitted on every verdict.
Prediction with error bar is the holdout score of the final promotion plus the calibrated band. Write it to the log before the hidden test is ever scored, so it is timestamped as a prediction.
Registry is runs/index.jsonl: run id, start, task, protocol hash, status, final scores. The aggregate views refuse to pool across differing hashes by reading this file alone.
10 · Synthetic benchmark was: Test fixtures
Theirs
Nothing — but it uses the same protocol schema as their task, so nothing built against it needs rewriting.
Ours
All of it.
Judges read
Technical, indirectly: "we measured our own false-positive rate before spending a GPU hour" is the robustness story.
What's decided
A small generated benchmark with the same funnel and rarity; deliberate failure injection; a second implementation of the task adapter.

How this is normally done
Generate users and items with latent factors, produce clicks at a few percent and conversions at a fraction of a percent of clicks, add a few categorical fields and one history list per user. That is enough to exercise every code path. The extra step that makes it a measurement tool rather than a smoke test:

Plant known effects
Include one feature with a true effect of a known size (say +0.01 AUC when used properly), one feature with zero effect, and one feature that leaks the label. Then the ladder's false-positive rate, false-negative rate and the leak audit's detection rate are all measurable in seconds, before any real GPU time is spent. It is a power analysis for the harness.

Nuances
Small but not too small. The fixture already showed that a tiny clicked subset makes CVR AUC unmeasurable. Size it so the clicked subset has a few thousand positives.
Failure injection through an environment variable read by the synthetic adapter, nowhere else. Not a flag the app can set, not a field in the protocol.
Same protocol schema, real values. protocols/synthetic.yaml is complete on day one and is what the app team builds against; the run registry shows task: synthetic so nobody reads its numbers as real.
11 · Naming standard
Rule: the product spec's names win. Where the backend introduced a different word for the same thing, the backend changes. Where the product spec has no name (data layer, runner), the backend name stands.

Concept	Product spec	Backend spec (old)	Use everywhere
The frozen ruler	Protocol	Benchmark profile	Protocol, protocol_hash, protocols/*.yaml, harness/protocol.py
Constraint set	rulebook	Rulebook	rulebook, rule_trip event
The stream	the log format	Event log	events.jsonl, heartbeat.jsonl
The tree of attempts	Run (tab), node	Search tree	tree, node; states per product spec
Ordered ideas	Hypotheses	queue	hypothesis, hypothesis_queued, queue_reordered
Per-node detail	node dossier	—	dossier
Belief machinery	noise band, promotion bar, ladder, leak audit	noise calibration, ladder, leak audit	band, bar, ladder, leak_audit
Literature work	Research, research pass, cache	researcher, research cache	research_pass_id, research_source, cache_lookup
Scoping	Brief	brief composer	brief
Transfer pairs	Audit → Replication	transfer recorder	replication
Spend	Audit → Cost	cost ledger	cost, slices researching | coding | training | tuning
Failures	Audit → Reliability	—	reliability, failure, recovery
Human touches	intervention count	open decision 3	intervention event
Live activity	now running, worker	heartbeat, worker id	heartbeat, worker
Export	Report	—	report
Fake task	synthetic benchmark	Test fixtures	synthetic
Whole execution	run, run id	run	run_id — note "Run" the tab vs "run" the execution is the one ambiguity the product spec carries; live with it, keep the tab capitalised
Repository layout, renamed
beating-nise/
├── data/                  ingest.py, schema.py, subsample.py
├── harness/
│   ├── events.py          the log
│   ├── protocol.py        was profile.py
│   ├── rulebook.py
│   ├── runner.py
│   ├── measure.py         band, ladder, leak audit
│   ├── tree.py            was search.py — tree + hypothesis queue
│   ├── audit.py           replication, cost, reliability projections
│   ├── outputs.py         submission, convergence, registry, report export
│   ├── agents/            researcher.py, coder.py, tuner.py, brief.py, cache.py
│   └── tasks/             base.py, synthetic.py, aliccp.py
├── protocols/             synthetic.yaml, aliccp.yaml
├── reference/             published_costs.yaml
├── runs/                  <run-id>/events.jsonl, heartbeat.jsonl, patches/
└── app/
Three vocabulary rules
Node states are the nine product-spec words and nothing else. "Failed" is not a state; it is a failure event on a node that is debugging.
Every user-visible string comes from the event's summary field. The app never composes its own sentence about a node.
"Baseline" means the organisers' pipeline only. Our own current best is "the incumbent". Conflating them is how a team ends up reporting a delta over the wrong thing.
Revised 26 Aug: §A gains a per-step work split; §5 gains the Optuna deep dive (v4.9 / v5-rc1, what it does not do); §6 research pass rebuilt on the 2021–2026 literature — provenance of every number stated, arithmetic corrected to Student-t, ladder v2 (reject-only screen, five seeds to certify, holdout picks the final), contested points listed; §7 rewritten on AIRA-dojo / FML-bench / AIRA2 / MARS / Gome — selection rule is second-order, greedy + fork-on-stall + hidden holdout is the defensible build. Four sourced write-ups in ~/Downloads. Earlier, 25 Aug (night): §6 rebuilt from a sourced research pass — three failure modes, threshold arithmetic, 4-rung ladder with numbers, run scorecard. Earlier: map redrawn to match the tree file-for-file, "hand-written" corrected to "frozen", THEIRS / OURS / JUDGES block on every section, app moved to build step 2, rulebook to step 10, two-person split, tuner/A100 routing and family taxonomy answered. Earlier the same day: file map and build order added at the top; sources for §1 linked; rulebook verdict, log streaming and CPU routing answered in §3–§5. Companion to product-spec.md and backend-spec.md. Verified baseline facts are in the earlier brief, Beating NISE; nothing here re-derives them.