<!--
The L4-v Runbook — generated 29 Aug 2026 from Execution_runbook.html
Regenerate: python3 tomd.py Execution_runbook.html
-->

> **Plain-text rendering of `Execution_runbook.html` (same directory), which is the authoritative source — the HTML carries the colour-coded status chips; the eight tests written to fail on the current tree are marked `⚠ fails today` in the test tables below.**
>
> Fourteen steps in dependency order. Companion to `Pivot_sequence.md`, which carries the architectural reasoning behind them.
>
> Facts marked `[TREE]` were verified against `beating-nise` at commit `3e22b28` on 29 Aug 2026.
> Facts marked `[GIVEN]` are inherited from the task-space page — re-verify before relying on one.
> Reconciled against `~/Downloads/kuairand-starter-kit/` on 29 Aug (`Runbook_reconciliation.md`) and re-verified against the tree, the kit README and `baseline_scores.json` on 30 Aug: splits are **temporal, not by user**;
> `evaluate.py` is the sole scoring authority and must not be reimplemented; the submission key is
> `row_id` (not `sample_id`), and `(user_id, video_id)` is **not** unique; numpy-only is the kit's choice, not a rule.
> 30 Aug additions: the "Start, end, and the number" section, step 6 before 4 and 5, the oracle date filter, test_features for the submission run, 50/6 h marked [statement].

---

_beating-nise · handoff document · written 29 Aug 2026 · verified against the tree and the kit 30 Aug_

# The L4-v Runbook

Fourteen steps in dependency order, from a repository that cannot yet address its own task to a run that can defend every number it reports. Written for an agent arriving cold, with no memory of the conversations that produced it.

- **Repo HEAD:** 3e22b28
- **Branch:** docs/phase-9-handoff
- **Open PRs:** 3 · #13 #16 #17 (30 Aug)
- **Suite:** collection error until pip install -e . · then 123 pass · 1 fail
- **Task adapter:** none for KuaiRand
- **Candidate on disk:** synthetic torch script · step 6 replaces it
- **Deadline:** 1 Sep 12:00

## Start, end, and the number  ·  _read first · verified 30 Aug_

Everything below serves one deliverable and one number. Hold both in view before reading any step. Companion pages: the file ecosystem map (every file, by folder, on-disk vs owed) and the starter-kit teardown.

> **WHERE YOU START · 30 AUG 2026**

HEAD 3e22b28 on docs/phase-9-handoff; three pull requests open (#13, #16, #17 — #11 was closed and #15 merged on 29 Aug). The harness below the task seam is finished and task-blind: events, protocol, measure, runner, tree, tuner, the LLM agents, the app. The seam is four methods on tasks/base.py — prepare, candidate_env, score(preds, split), rows(split) — plus TaskPaths. Nothing above the seam exists for KuaiRand: no tasks/kuairand.py, no data/kuairand.py, no protocols/kuairand.yaml, and candidate/template.py is still the synthetic candidate — a torch MLP over parquet that writes sample_id, p_click, p_conversion_given_click. The word KuaiRand appears nowhere in the tree. Two small leaks below the seam: __main__.py hardcodes SyntheticTask, and runner._build_env asserts only TRAIN, VALID may cross.

> **WHERE YOU END**

Three artefacts, produced by an unattended run. (1) runs/<run_id>/submission.csv — one score per test row (29 Apr – 8 May), columns row_id,user_id,video_id,score, accepted by the kit’s submit.py --check --split test. (2) runs/<run_id>/events.jsonl and a per-iteration export folded from it: hypothesis, diff, validation score, oracle delta, errors and recoveries, tokens, wall-clock. (3) The write-up, every number of which is one command against that log, led by an autonomy rung that claim_level() computed — never typed.

> **THE NUMBER**

The organisers score primary − 0.5946 on the hidden test split, where primary = mean(GAUC, nDCG@5) from their evaluate.py and 0.5946 is their FM baseline on test. You never compute that number. Your proxy is valid (22 – 28 Apr), where FM scores 0.6016. The published ladder — random 0.4834 → 0.4753, popularity 0.5807 → 0.5715, FM 0.6016 → 0.5946 — drops a steady 0.007 – 0.009 from valid to test, so a valid gain is a sound predictor of a test gain. A win is a gain of at least ε = 0.002 over the incumbent; seed noise is σ ≈ 0.0008, so anything under 2σ is noise. Headroom is 0.27 to the oracle ceiling (0.8484 valid), not 0.40 to 1.0.

### The rules, with where each one comes from

- `[TREE]` Splits, metric, submission format, convergence. train 0408–0421 / valid 0422–0428 / test 0429–0508; evaluate.py is the sole scorer; row_id,user_id,video_id,score in data.load() order; stop when three consecutive rounds improve valid primary by less than 0.002 (baseline_scores.json → convergence_rule). Verifiable in ~/Downloads/kuairand-starter-kit/.
- `[TREE]` The random-exposure log is a sanctioned validation set. README §从哪里开始改, direction 7: log_random_4_22_to_5_08_pure.csv “can serve as an additional unbiased validation set, to check whether the model only overfits biased traffic”. That is the oracle. It is inside KuaiRand-Pure, so it is not external data, and it is never trained on.
- `[PAGE]` No external training data. No hidden-test access during development — the agent develops on the training split and the public validation feedback only. At most 50 iterations and 6 hours wall-clock. Per-iteration run logs. These come from the organisers’ problem statement shared on 29 Aug, which is not on disk — before enforcing 50 or 6 h, re-read its wording (iterations or trained candidates? agent time or total?).
- `[PAGE]` Judging: Technical 35 · Innovation 20 · Autonomy 20 · Cost 15 · Presentation 10. The test delta sits inside Technical; the logs, the unattended loop, tokens and wall-clock, and the write-up carry the other 65.

> **TWO WORDS THAT MEAN TWO THINGS**

“Oracle” in this document = the random-exposure log used as a second validation signal (the kit’s direction 7). “Oracle” in the kit = the perfect-ranking ceiling, primary 0.8645 on test (“评估进展请以 oracle 为分母”). In the write-up call ours the random-exposure gate, so a judge does not read “oracle” as “they used the labels”. The yaml below keeps both: holdout_validation is our gate, baseline.published.oracle_ceiling is theirs.

“Holdout” in the code = the seat our oracle sits in (TaskPaths.holdout_validation, score(preds, "holdout"), holdout_report()). There is no separate oracle rung; wherever this page says “the oracle rung” it means the holdout path.

### The five stages, and who owns each

- Load (kit data.py) — wrap, never rewrite: row order is the law. Ours, once, in step 2.
- Encode — free. Lives inside the candidate; hypotheses change it. Steps 6 and 13.
- Model — free, the whole point. The file the loop edits. Steps 6 and 13.
- Evaluate (kit evaluate.py) — untouchable. Imported by the adapter, called harness-side with labels the candidate never had. Step 3.
- Submit (kit submit.py) — untouchable format. Written by outputs.write_submission, read back through read_submission. Steps 3.5 and 14.

### The three phases, and what each gate measures

| Phase | Steps | What is true at the end | Measured by |
|---|---|---|---|
| Make the measurement true | 1 · 2 · 3 · 6 · 4 | The real data is on disk with digests; the harness scores a real candidate on valid with the kit’s own function; the oracle path exists and labels never cross the wall. | Three reference predictors land at 0.4834 / 0.5807 / 0.6016 on valid; the FM template reproduces ~0.6016; a fake run emits a verdict carrying both deltas. |
| Make the loop honest | 5 · 7 · 8 · 9 · 10 · 11 · 12 | Thresholds are multiples of a measured σ; rules are enforced before a token is spent; numbers carry provenance; memory round-trips; attribution is computed; the move policy is replayable; the autonomy claim is derived. | Each step’s fails today test flips; counters at zero where the design claims free; the golden-run fixture. |
| Spend the result | 13 · 14 | One unattended run on KuaiRand; a submission the kit’s checker accepts; a write-up every number of which is a fold over the log. | submit.py --check --split test green; every write-up number reproducible by one command. |

Order of execution: 1 → 2 → 3 → 6 → 4 → 5 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14. Step 6 moves ahead of 4 and 5 because nothing after step 3 can run a real candidate until the synthetic template is replaced. Step numbers are kept so every cross-reference on this page stays valid.

## How the files wrap the task  ·  _start here · the wall, the files, the protocol_

The harness never touches the model. It touches files, three environment variables, and one scoring function. The picture below is the whole wiring: which file feeds which, and which side of the wall each one sits on. The folds under it hold the detail — open them when you need a name or a key, not before.

[diagram — see the HTML/artifact version. Labels: STARTER KIT · ~/Downloads/kuairand-starter-kit/ · REPO · ~/beating-nise/ · above the wall = the candidate can read · below the wall = harness only · KuaiRand-Pure/data/ (raw) · log_standard_4_08_to_4_21 · train · log_standard_4_22_to_5_08 · valid+test · log_random_4_22_to_5_08 · ORACLE · video_features_basic · data.py · load · encode · evaluate.py · the score · submit.py · read_submission · baseline.py · FM self-check · data/kuairand.py · build once (step 2) · wraps data.py, never sorts · data/kuairand/ · train.csv · has long_view · search_validation.csv · no label · oracle_features.csv · no label · row_id first, kit order · test features 0429–0508 → harness_only/ · labels never written · scored once, at submission · candidate/template.py · the candidate = a script · reads $TRAIN $VALID [$ORACLE] · honours $SEED · numpy + csv · no torch · no network jail (!) · preds.csv · row_id,user_id,video_id,score · harness/runner.py · _build_env → Popen(template) · asks the adapter for the 3 paths · THE WALL · only TRAIN · VALID · ORACLE cross; any value naming holdout / rulebook / protocols is dropped · protocols/kuairand.yaml · digests · splits · ε=0.002 N=3 · σ (step 5) · hashed per event · data/kuairand/harness_only/ · search_labels.csv · valid · oracle_labels.csv · random log · digests.json · harness/tasks/kuairand.py · prepare · candidate_env · score · rows · only file that knows KuaiRand · harness/measure.py · verdict vs incumbent, σ-scaled · runs//events.jsonl · append-only · all state is a fold · runs//submission.csv · written, read back, then emitted · candidate/rules.jsonl → verify.py · C1–C9 + 3 seeded dead ends · reads, via data.py · writes 3 label-free CSVs · writes labels · reads · env: TRAIN VALID ORACLE · + SEED · nothing else · writes · score(preds, split) · joined by row_id · labels · verifies digests · imported by score() · never copied or edited · read_submission · --check must pass · ↑ gauc · ndcg · primary · outputs.py · gate before any run]

_Which file links to which. Above the red line: files the candidate script can read and the one it writes. Below: files only the harness opens. Two things sit on the line — data/kuairand.py writes to both sides once, and runner.py is the gate that hands exactly three paths across it every run. The blue arrow is the only thing that crosses downward: the candidate’s predictions, scored by the adapter against labels the candidate never saw._

### In one breath

- Kit → repo, once. data/kuairand.py reads the four raw CSVs through the kit’s own data.py and writes three label-free files the candidate may read (data/kuairand/*.csv) plus the label files it may not (harness_only/). Test features go under harness_only/ for the final submission run; test labels are never written.
- Every run. runner.py asks the adapter for the three paths, puts them in an env with SEED, and launches candidate/template.py as a subprocess. The script trains and writes preds.csv.
- Scoring. The adapter harness/tasks/kuairand.py joins preds.csv to the harness-only labels by row_id and calls the kit’s evaluate(). It is the only file in the repo that knows what KuaiRand is.
- Judging and memory. measure.py turns the number into a verdict; events.jsonl records it; everything else — lessons, monitors, the L4-v claim, the write-up — is computed from that log.
- Before any run. rules.jsonl is checked against the patch by verify.py; a candidate that names a label column, a raw kit file, or a dead end never starts.

**Every file, by side of the wall — the full table**

| File | Role | Written by | Read by | Candidate sees? |
|---|---|---|---|---|
| ~/Downloads/kuairand-starter-kit/KuaiRand-Pure/data/*.csv | Raw kit data: log_standard_4_08_to_4_21 (train), log_standard_4_22_to_5_08 (valid + test in one file), log_random_4_22_to_5_08 (the oracle), video_features_basic | Zenodo download (step 2.1) | data/kuairand.py build, once | No. Symlinked to data/raw/ for the build only; rule C9 forbids the filenames |
| protocols/kuairand.yaml | The ruler: digests, splits, metric, ε/N, σ. Hashed into every run | You (step 3.1); step 5.3 appends σ | protocol.load → adapter prepare(), events.py:60 (run header), measure.py:264 | No — _build_env drops any value containing protocols/ |
| data/kuairand/train.csv | data.load()["train"], 0408–0421, with long_view, row_id first column | data/kuairand.py | candidate via $TRAIN | Yes |
| data/kuairand/search_validation.csv | data.load()["valid"], 0422–0428, no label column | data/kuairand.py | candidate via $VALID | Yes |
| data/kuairand/oracle_features.csv | The random-exposure log, 0422–0428 only (valid’s window — the raw file runs into the test dates), every label column stripped | data/kuairand.py | candidate via $ORACLE, holdout rung only | Yes, holdout rung only |
| data/kuairand/harness_only/search_labels.csv | row_id, user_id, video_id, long_view for valid | data/kuairand.py | kuairand.score(preds, "search") | Never |
| data/kuairand/harness_only/oracle_labels.csv | Same four columns for the random log | data/kuairand.py | kuairand.score(preds, "holdout") | Never |
| data/kuairand/harness_only/digests.json | Computed SHA-256 of every file above, written at prepare() | adapter prepare() | tests, the write-up | Never |
| data/kuairand/harness_only/test_features.csv | The test split, 0429–0508, features only — the rows the submission must score. No test label is written anywhere | data/kuairand.py | outputs.write_submission (step 3.5): the winning node’s template is run once more with VALID pointed here | Once, after the search has stopped, as the final run’s VALID; the event log records it |
| harness/tasks/kuairand.py | The adapter: prepare / candidate_env / score / rows. The only file that knows KuaiRand exists | You (step 3.2) | runner.py (candidate_env at 537, score at 390), __main__.py | No |
| kit evaluate.py | The definition of the score. Imported, never copied, never edited; its SHA-256 is pinned in the protocol | organisers | kuairand.score() only | No |
| kit submit.py | read_submission = the organisers’ definition of a valid prediction file | organisers | outputs._readback_predictions (step 3.5), kuairand.score() preamble | No |
| candidate/template.py (candidate/kuairand/ after 6.0) | After step 6. Today it is the synthetic torch script. The script the researcher mutates and the runner executes. Reads $TRAIN $VALID [$ORACLE] $SEED, writes preds.csv | step 6, then every hypothesis patch | runner.py:188 as a subprocess | It is the candidate |
| candidate/rules.jsonl | Nine contract rules + three seeded dead ends | steps 6, 13 | harness/verify.py (step 7) before any run | No — rulebook is a dropped token |
| hypotheses/bank.yaml | Cold-start proposals, sorted by p_win | step 13.1 | tree.py Queue | No |
| runs/<run_id>/events.jsonl | Append-only log; the run header carries the whole protocol; every other state is a fold over this | events.py | everything: memory, monitors, claim_level(), the write-up | No |
| runs/<run_id>/<node>/workspace/preds.csv | row_id,user_id,video_id,score in $VALID (or $ORACLE) row order | the candidate | kuairand.score() | Writes it |
| runs/<run_id>/submission.csv | Final artefact; read back through submit.read_submission before submission_written is emitted | outputs.write_submission | the organisers | No |

**One rung, as file traffic**

```
tree.py        picks (node, rung)                                        reads  bank.yaml, lessons.jsonl (via events)
verify.py      static regex → shape → llm over the patch                 reads  rules.jsonl          [step 7]
runner.py      paths = task.prepare(protocol, root)      once per run    reads  protocols/kuairand.yaml, data/raw/*
               env   = _build_env(task.candidate_env(paths, rung))       ← {TRAIN, VALID, ORACLE?} + SEED, nothing else
               Popen(candidate/template.py, env)                         reads  $TRAIN $VALID [$ORACLE]; writes preds.csv
               metrics = task.score(preds.csv, spec.score_split)         reads  harness_only/{search,oracle}_labels.csv → evaluate()
measure.py     verdict from metrics["primary"] vs incumbent, σ-scaled    reads  nothing on disk; constants + protocol.calibration
events.py      append verdict {delta_mean, oracle_delta, visit, seeds}   writes events.jsonl
tree.py        _append_lesson → lessons.jsonl; queue re-sorted           writes lessons.jsonl
```

**protocols/kuairand.yaml — what the loader enforces, and what it does not**

- `[TREE]` protocol.load (harness/protocol.py:25) checks exactly four top-level keys exist — schema_version, task, ruler, run — and that ruler is a non-empty dict. Nothing else is validated. Nulls are allowed anywhere under ruler.
- `[TREE]` protocol_hash = "sha256:" + sha256(canonical_bytes(ruler)) — keys sorted recursively, floats via repr, None → null. The run block is excluded from the hash. So adding σ under ruler.calibration in step 5 changes the hash (correct: different thresholds = different experiment); changing run.budget does not.
- `[TREE]` The whole protocol — ruler and run — is written into the run-header event (events.py:60–63). That is what makes events.jsonl self-describing: the yaml is documentation that the log carries, and the hash is what ties every verdict to one ruler.
- `[TREE]` Only five ruler keys are read by code, and they are read by the adapter, not the loader (synthetic.py:205–211): data.train.sha256, data.test.sha256, splits.search_validation.sha256, splits.holdout_validation.sha256, scoring.script_sha. Each is compared to the digest computed from disk at prepare(); a mismatch raises sha256 mismatch for <key>. A value that parses as hex ≤ 15 (PLACEHOLDER_MAX, e.g. 000…0001) is a placeholder and skips verification; the string pending is not hex, so it fails as a mismatch. This is why test_no_placeholder_digests exists: a placeholder is a bypass, not a TODO.
- `[TREE]` fake and --rows ≠ 1_000_000 overwrite exactly those five key paths with placeholders (__main__.py:121–126). Keep the same five key paths in kuairand.yaml or fake mode raises KeyError. Add new keys beside them; do not rename them.
- `[TREE]` measure.py:264 reads run.measure_timeout_s (default 600). Nothing reads seeds, baseline, metrics, rulebook_version, scoring.aggregation or run.budget.* — they are documentation carried into the log header. The GPU-hours cap comes from the CLI --budget, not the yaml.
- `[TREE]` Nothing reads convergence either. outputs.Convergence(eps, n_rounds) takes explicit arguments (and is a stub on main; #16 fills it). Step 3.1 writes 0.002 / 3 into the yaml; whoever constructs Convergence must pass protocol.ruler["convergence"]["epsilon"] and ["n_rounds"] — the runbook’s test_epsilon_and_n_are_not_derived should assert that path, not just the literals.
- `[TREE]` There is no task registry. __main__.py:153 and :333 hardcode SyntheticTask(n_impressions=args.rows); protocol.task is used only for the run id and the researcher brief. Step 3’s “register the adapter” means: dispatch on protocol.task in __main__.py, or the yaml’s task: kuairand selects nothing.

**protocols/kuairand.yaml — the file, exactly**

Same five enforced key paths as synthetic.yaml, KuaiRand meanings, plus the blocks steps 3 and 5 add. Every sha256: below is filled from shasum -a 256 in step 2; none may be a placeholder in a real run.

```
# protocols/kuairand.yaml — written in step 3.1, σ appended in step 5.3.
# ruler is hashed into every event; run is not.
schema_version: 1
task: kuairand                                # must select the adapter in __main__.py (no registry today)

ruler:
  rulebook_version: 4                         # bump: rules.jsonl changed (C1/C2/C3 retargeted, C8, C9, 3 seeded dead ends)
  data:                                       # RAW kit files. digests of the downloads, before any split is written.
    ingest_hash: kuairand-pure-zenodo-10439422
    train:                                    # key path read by prepare() — keep the name
      source: KuaiRand-Pure/data/log_standard_4_08_to_4_21_pure.csv
      sha256: <fill>
    test:                                     # key path read by prepare() — keep the name. this raw file holds valid AND test;
      source: KuaiRand-Pure/data/log_standard_4_22_to_5_08_pure.csv   # its test-dated rows are never written anywhere
      sha256: <fill>
    random_log:                               # the oracle's source. new key; not read by fake mode
      source: KuaiRand-Pure/data/log_random_4_22_to_5_08_pure.csv
      sha256: <fill>
      rows: null                              # fill on download; README says ~1.18 M
    video_features:
      source: KuaiRand-Pure/data/video_features_basic_pure.csv
      sha256: <fill>
  splits:                                     # WRITTEN files. temporal, from data.py SPLITS, file order preserved, row_id 0-based.
    train:
      rule: "date 20220408..20220421 of data.train, via data.load()"
      rows: 1141112
      file: train.csv
      sha256: <fill>
    search_validation:                        # key path read by prepare() — keep the name
      from: test                              # i.e. the second raw file
      rule: "date 20220422..20220428, via data.load()['valid']; label column stripped candidate-side"
      rows: 124909
      file: search_validation.csv
      labels: harness_only/search_labels.csv
      sha256: <fill>                          # digest of the candidate-visible file
    holdout_validation:                       # key path read by prepare() — keep the name. THIS IS THE ORACLE.
      from: random_log
      rule: "random-exposure log rows dated 20220422..20220428 (VALID's window), file order; every label column stripped candidate-side"
      file: oracle_features.csv
      labels: harness_only/oracle_labels.csv
      sha256: <fill>
    test:
      rule: "date 20220429..20220508 — features written under harness_only/ for the submission run; labels never written, never scored by the harness"
      file: harness_only/test_features.csv
      labels: null
  metrics:
    primary:
      definition: "mean(GAUC, nDCG@5) as computed by the kit's evaluate.py"
      population: all_impressions
      positive: long_view
      output: score                           # any real; only within-user order matters
      grouping: user_id
      components: [gauc, ndcg_at_5]           # score() must return both — step 10 reads them
  scoring:
    script_sha: <fill>                       # key path read by prepare(): sha256 of harness/tasks/kuairand.py
    evaluate_sha: <fill>                     # sha256 of the kit's evaluate.py — pinned, test_score_delegates_to_kit_evaluate
    submit_sha: <fill>                       # sha256 of the kit's submit.py — the read-back contract
    prediction_columns: [row_id, user_id, video_id, score]
    aggregation: mean_absolute_delta
  baseline:
    repo: kuairand-starter-kit
    command: "python3 baseline.py --model fm"  # k=16 lr=0.001 batch=8192 max_epochs=40 patience=4
    published:                                # from baseline_scores.json
      valid: {gauc: 0.6674, ndcg_at_5: 0.5357, primary: 0.6016}
      test:  {gauc: 0.6610, ndcg_at_5: 0.5282, primary: 0.5946}   # leaderboard; never produced by the harness
      random_valid: 0.4834
      popularity_valid: 0.5807
      oracle_ceiling: {valid: 0.8484, test: 0.8645}
    reproduced:
      valid: []                               # step 3.6 fills: five seeds of the FM template through score()
  composition:                                # step 2.2 fills valid; test is the organisers' figure
    test:  {no_positive_pct: 27.1, all_positive_pct: 9.2, no_pair_pct: 36.3, users: 23875}
    valid: {no_positive_pct: null, all_positive_pct: null, no_pair_pct: null, users: null}
  convergence:                                # organisers' rule. NOT tuned. must be passed to outputs.Convergence explicitly.
    epsilon: 0.002
    n_rounds: 3
  calibration:                                # step 5.3 appends. changes the hash — intended.
    sigma: null                               # sd of primary over five seeds of the unchanged baseline, valid split
    sigma_seeds: [1, 2, 3, 4, 5]
    multipliers: {sigma_unstable: 6, screen_reject: -2, promote_floor: 2}
    ladder_eta: eps                           # pinned to convergence.epsilon, not σ-derived
    measured_on: null                         # date + machine
  seeds:
    pinned: [data_shuffle, init]              # numpy FM has no dropout
    cuda_deterministic: false                 # no CUDA anywhere in the pipeline

run:                                          # not hashed. only measure_timeout_s is read by code.
  measure_timeout_s: 600
  budget:
    wall_clock_h: 6                           # [statement] the organisers' cap. not on disk — re-verify the wording. denominator is wall-clock now
    max_iterations: 50                        # [statement] same source; --max-nodes must stay ≤ this (step 13 uses 20)
    llm_usd: null
  workers: 1
```

> **TWO THINGS THE WALL DOES NOT DO**

It does not stop a candidate from opening a path it was not given. The subprocess inherits the machine’s filesystem and network; the defences are the three-variable whitelist, the absent label files, rule C9 on the raw filenames, and the oracle gap that would expose memorised validation. A candidate that downloaded the dataset itself and hard-coded answers under obfuscated names would pass all four. If you want this closed, run the subprocess under unshare -n (Linux) or with HTTP_PROXY=HTTPS_PROXY=127.0.0.1:9 and an empty HOME, and add test_candidate_has_no_network. One line at runner.py:188; not in the fourteen steps, worth doing before step 13.

It does not validate the protocol. Four keys and a non-empty dict is the whole check. The yaml is a contract between you and the adapter, enforced by the adapter’s prepare() and by the tests in steps 2, 3 and 5 — not by the loader.

## Read this first  ·  _orientation_

This document assumes you have not read the companion pages and cannot ask anyone questions. It is written so that you can start at any step, verify where you actually are rather than where you were told you are, and rebuild the reasoning behind a decision before changing it.

> **THE ONE-SENTENCE GOAL**

Turn a search loop that grades its own homework into one whose every promotion is checked against a data split the search could not influence — so that the claim at the top of the submission is a derived fact rather than an assertion.

In the vocabulary of the verification-gap survey (arXiv:2608.05179), that is the move from L4-m, mechanically closed on its own metric, to L4-v, validated from outside the search. Almost every published autonomous-ML system sits at L4-m and reports its own metric back to itself. The gap is the contribution.

### Provenance markers

Every factual claim in this document carries one of four markers, because a runbook that mixes verified facts with inherited assumptions is how drift starts. When you act on a fact, check its marker first.

- `[TREE]` Verified in the repository on 29 Aug 2026, with a file and line. If the line has moved, the fact may still hold — search for the symbol, do not assume it was deleted.
- `[PAGE]` Inherited from the task-space and research-space pages that preceded this one. Numbers about the dataset and the baselines live here. Re-verify before you build a decision on one.
- `[PAGE]` Quoted from the organisers’ problem statement, shared on 29 Aug and not on disk. Four facts carry it: no external training data, no hidden-test access during development, 50 iterations, 6 hours. Re-read the statement before enforcing a number from it.
- `[TODO]` Not yet known. A number that must come out of a run rather than out of a document. If you find yourself typing a value into a slot marked like this, stop — that is the exact failure this project exists to avoid.

### Invariants — never break these, whatever the clock says

- No state that is not a fold over events. The append-only JSONL log is the only source of truth. Anything you cannot recompute from the log by replaying it does not exist, and cannot be claimed in the write-up.
- A model may forecast; only the measurement layer may report. Every number in a verdict comes from task.score. A model’s estimate lives in an expected_* field and never crosses into a verdict.
- The candidate never receives a path to a label it is being scored on. This is enforced by an assertion, not by discipline, and the assertion is a deliverable in its own right.
- Nothing is promoted on a number alone. A promotion needs the number, three seeds agreeing, and the declared observables having moved.
- If a claim weakens, the report weakens with it. The autonomy level is computed from the log. Never type a rung into a template.

> **IF YOU ONLY HAVE FOUR HOURS**

Do steps 1, 2, 3, 6, 4 and 13 and stop. That path produces a real measured result on the real task with a trustworthy instrument, which is a complete if modest submission. Everything from step 5 onward makes the loop better; steps 1–4 and 6 make the measurement true, and a better loop measured badly is worth nothing.

## Conventions and contracts  ·  _read before step 1_

Everything an agent needs that is not specific to one step. If a step’s instructions seem to assume something, it is assumed here.

### Set up, and how to run anything

```
# from the repository root — /Users/ngchenmeng/beating-nise
python -m pip install -e .        # all deps are declared in pyproject.toml
pytest -q                          # default addopts is -m 'not slow' → 11 deselected
pytest -q -x --ff                  # while iterating: last-failed first, stop on first
pytest -q tests/test_05_measure_pure.py::test_attribution_gate    # one test
pytest -q -m slow                  # the deselected ones, synthetic task only

# the harness CLI — four subcommands, no others
python -m harness init protocols/kuairand.yaml       # creates runs/<task>-<utc-stamp>/
python -m harness fake --instant                     # event-log smoke, no training
python -m harness run-one --protocol protocols/kuairand.yaml --seed 1 --timeout 300
python -m harness run protocols/kuairand.yaml --max-nodes 20 --rows 1000000 --epochs 12
```

> **BRANCH DISCIPLINE**

Never commit to main directly. One branch per step, named for it — step-04-eval-integrity — then a pull request. The exception is step 1, which merges pull requests that already exist. If you are about to run git push origin main, you have skipped this paragraph.

### The candidate contract

The candidate is a standalone script the harness copies into a workspace and runs as a subprocess. It must not import the harness package. It talks to the harness through environment variables in and three report calls out. Getting this wrong is the most common cause of a run that fails in a confusing way.

| Direction | Name | Meaning |
|---|---|---|
| env in from the task | TRAIN | Path to the training split. Always present. |
| VALID | Path to the search-validation split. Always present. |  |
| ORACLE | Path to the random-exposure features. Added in step 4; present only on the holdout path (the oracle’s seat — there is no separate oracle rung). Never contains a label column. At submission time VALID, not ORACLE, is pointed at the test features (step 3.5). |  |
| HOLDOUT | Never present. runner.py pops it and asserts the task did not supply it. |  |
| env in from the run config | SEED | Must reach data shuffling, initialisation and dropout. Rule C4 enforces that you read it. |
| DEVICE | cpu for this task. |  |
| WORKSPACE | Where to write predictions and checkpoints. |  |
| EPOCHS | 1 on the smoke rung, the protocol value elsewhere. |  |
| BATCH | Batch size. The retry table halves this on an out-of-memory failure. |  |
| LR | Learning rate. |  |
| FEATURES | Comma-separated list, or the literal base. |  |
| report out | report.progress(step, total, loss) | Every epoch. The stall watchdog and the divergence check both read this; a candidate that goes quiet is killed. Rule C5. |
| report.checkpoint.save(step, blob) | Enables resume and sensitivity checks. Rule C6. |  |
| report.result(metrics, preds_path) | Once, at the end. The harness scores preds_path itself and ignores your metrics for any verdict. |  |

> **TWO TRAPS IN THE ENVIRONMENT BUILDER**

runner._build_env filters the inherited environment by value as well as by name: any variable whose value contains holdout, rulebook or protocols/ is dropped, case-insensitively. So the oracle features file must not live at a path containing any of those words, or the variable will silently vanish and the candidate will fail with a confusing KeyError.

It also removes the repository root from PYTHONPATH, which is what stops a candidate importing the harness. If you find yourself adding it back to make an import work, the import is the problem.

### Definition of done, for any step

A step is finished when all five are true. Four out of five is not four-fifths finished; it is a step that will be re-opened by the next agent.

- The files in the step’s manifest exist with the stated action applied, and nothing outside the manifest changed.
- The step’s tests pass, and any test marked fails today was observed failing before it passed. Run it on the previous commit if you need to see it.
- The full suite is still green. pytest -q, not just the new file.
- The gate command produces the stated output. Not something close to it.
- The branch is pushed and a pull request opened, its description naming the step number.

## Where am I?  ·  _drift recovery_

Run these six commands before doing anything else. They read the tree rather than trusting this document, and between them they identify which step is actually next. If a command’s answer disagrees with the state written in a step below, the tree is right and this page is stale.

```
# 1 — is the tree one tree?
gh pr list --state open --json number,mergeable
   3 open (#13 #16 #17)     →  you are before step 1   (30 Aug state; #11 closed, #15 merged)

# 2 — does the suite pass?
pytest -q --ignore tests/test_07_tuner.py 2>&1 | tail -3
   "Interrupted: 1 error during collection" without --ignore is the
   optuna import (F6) — pip install -e . first, then drop the --ignore
   any failure               →  finish step 1 before anything else

# 3 — does the task exist?
ls protocols/ harness/tasks/
   no kuairand.yaml          →  you are before step 3

# 4 — is the instrument honest?
grep -n 'score(preds, ' harness/runner.py
grep -n 'candidate_env(paths)) <=' harness/runner.py
   literal "search"          →  step 4 not done
   allowlist without ORACLE  →  step 4 not done

# 5 — is the loop honest?
grep -rn 'ATTRIBUTION_HAND' harness/
   found                     →  step 10 not done

# 6 — has anything actually run?
ls runs/ 2>/dev/null | grep -i kuairand | tail -5
   empty                     →  step 13 not started
   (runs/ already holds fake-0001 and two synthetic-* runs — do not count them)
```

> **THE THREE DEFECTS YOU WILL NOT FIND BY READING**

All three look like working code. Each is a place where a mechanism is fully built and permanently disabled, so tests pass, logs look healthy, and nothing warns. They are the reason this runbook exists, and if you skip ahead you will re-derive them the hard way.

- Attribution is a constant. tree.py:51 sets ATTRIBUTION_HAND = "clear", and that is what reaches every verdict. The gate that consumes it works perfectly. It has simply never been given anything but a pass. [step 10]
- The rules file has no reader. candidate/rules.jsonl declares seven constraints; nothing in harness/ opens it. The only reference in the repository is a test asserting it is valid JSON. [step 7]
- The memory delivers blank lines. tree.py:432 writes lesson rows keyed node, family, delta, gpu_min, diff_summary. researcher.py:165 reads heading and text. Every lesson reaches the model as the string - lesson: and nothing after it. [step 9]

## Pre-flight audit  ·  _nine corrections · 29 Aug_

A last pass comparing the planned code against the capabilities it is supposed to deliver, and against the tree it will land in. Nine things were wrong or missing. Two would have cost the first hour, one would have failed at the very last moment, and three are chains of small edits that a step named only one link of. All are fixed in the steps below; they are listed here so the reasoning survives.

> **A · PR #16 STRICTLY CONTAINS PR #13**

Verified with git merge-base --is-ancestor: #13’s tip is an ancestor of #16, and there are zero commits in #13 that are not in #16. The two branches touch the same nine files. The earlier instruction — merge #13 first, alone, then #16 — would have merged the same work twice and invited a conflict on every file.

Correct order: close #11, merge #16, watch #13 close itself as already-merged, then #15 and #17 in either order (independent, and they touch only app/static/ and context/). 30 Aug: #11 is already closed and #15 already merged; only #16 → #13 closes itself → #17 remain.

> **B · #16 DELIVERS FAR MORE THAN THE RUNBOOK CREDITED IT WITH**

harness/outputs.py and harness/audit.py are entirely stubs on main — ten functions raising NotImplementedError between them, including the submission writer, the convergence rule and the report generator. #16 implements all of them and wires two into the tree: Convergence at tree.py:406 and write_submission at tree.py:722.

So the organizers’ stop rule and the thing that writes the actual deliverable arrive in step 1, not step 14. Step 14 calls outputs.report(); it does not write one.

> **C · THE SUBMISSION WRITER WILL REJECT EVERY VALID KUAIRAND SUBMISSION**

_readback_predictions in #16 requires the column p_conversion_given_click, explicitly rejects p_click_and_conversion, and calls task.rows("test") — a split name the adapter’s rows() mapping does not have. It is the same defect as rule C3: a task-specific validator inherited from Ali-CCP.

This one is nasty because of when it fires. Everything works, the run completes, and the failure lands at the moment the submission is written — with the deadline in sight. It is now retargeted in step 3 rather than discovered in step 14.

> **D · THE HOLDOUT BUDGET IS ENFORCED IN TWO PLACES, ONE OF THEM HARDCODED**

tree.py:592 reads if self.measure._holdout_visits >= 2: — a literal, not the constant. Changing HOLDOUT_VISITS_MAX in measure.py alone, which is what step 4 previously said, would have left the tree still gating at two visits. The run would stop consulting the oracle after the second promotion and nothing would say why. The fix is not to repoint the literal at the constant but to delete the duplicate check — measure.py:460 already raises HoldoutBudgetExceeded, and a rule enforced in one place cannot drift.

> **E · HOLDOUT IS DELIBERATELY NOT A LADDER RUNG &MDASH; AND THAT IS GOOD NEWS**

measure.py:349 raises RungMismatch("holdout is not a ladder rung; use holdout_report()"). It has its own path with its own seed set and its own visit accounting. The earlier plan added "oracle" to RUNG_SPECS, which fought this design.

The oracle should reuse holdout_report(). Less code, and it inherits the visit counting, the seed policy and the budget exception for free — which is exactly the accounting step 12 wants to report.

> **F · &LDQUO;ADD ORACLE&RDQUO; IS THREE EDITS, NOT ONE &MDASH; AND NOT A NEW RUNG**

Widening the capability wall was written as a one-line change. Because the oracle is the holdout slot (E above: TaskPaths.holdout_validation binds to the random-exposure log, and after #16 score_split="holdout" already exists), the Rung literal at types.py:21 and the Literal["search","holdout"] on Task.score do not change. What does: a new oracle_features field on TaskPaths, rung-awareness in candidate_env, and the wall itself — which also means synthetic.py has to stay conformant to the Protocol or the whole suite fails.

> **G · THE HYPOTHESIS TYPE HAS NO SEAT FOR WHAT STEPS 9 AND 10 NEED**

Hypothesis carries id, stage, mechanism, description, citation, expected_gain, expected_gpu_h, parent_node and patch. Step 9 uses hyp.pattern; step 10 uses hyp.claim. Neither exists, and researcher.HYPOTHESIS_SCHEMA validates the model’s output against the old field list, so it would reject the new ones. Three edits, now named in step 10.

> **H · ATTRIBUTION&RSQUO;S EVIDENCE IS SELF-REPORTED BY THE THING BEING JUDGED**

The sharpest problem the audit found, and it is architectural rather than a missing line. Two of the three observables for the pairwise hypothesis — train_logloss and valid_pairs_per_epoch — can only come from inside the candidate, via the metrics dict on report.result. So a generated candidate supplies the evidence used to decide whether that candidate’s story is true. A candidate that reported a plausible pair count would pass attribution while doing nothing of the kind.

The rule that fixes it: every claim must include at least one observable computed harness-side from task.score — for the pairwise hypothesis, the comparison of GAUC movement against nDCG movement. Candidate-reported observables may corroborate; they may never be the only evidence. It is one assertion in the proposal gate and it closes the hole.

> **I · THE ROUND POLICY AND THE TOPOLOGY FUNCTION DISAGREE ABOUT BREADTH**

The round is described as screening all survivors, three at a time. select() returns one move, and the protocol sets workers: 1. Both are defensible; they are not both true at once. Resolution: the loop calls select() repeatedly until it returns the at-branch-cap move, giving three in flight, and the runs within a round are sequential on one core — three screens at forty seconds is two minutes, which is what the ten-minute round budget already assumed.

> **WHAT THE AUDIT DID NOT FIND**

No capability is unbuilt. All ten have a step, tests and a gate, and the eight tests written to fail on the current tree still fail for the reasons stated. The corrections above are about sequencing, type plumbing and one evidence-provenance hole — not about a missing mechanism.

## How the tests are written  ·  _anti-short-circuit doctrine_

A test suite that can be satisfied without building the thing is worse than no suite, because it converts an unfinished system into a confident one. Every test named in this runbook obeys the eight rules below. If you add a test, it obeys them too; if you find yourself weakening one to get green, you have found a design problem rather than a test problem.

| Rule | What it blocks |
|---|---|
| 1 · Assert on the event log, not on a return value. | A function that returns the right thing and never records it. The submission’s claims are all statements about the log, so the log is what must be correct. |
| 2 · At least one test per capability must fail on the current tree. | Tests written to describe what already happens. A test that was green before the work started tested nothing about the work. Four such tests are marked in red below — run them first and watch them fail, or you have not proven they can. |
| 3 · Mock the boundary, never the subject. | Mocking measure or task.score. The LLM and the clock may be faked; the measurement layer may not, because it is the thing under test in almost every case. |
| 4 · Every affirmative test has a refusal twin. | A guard that passes everything. X is accepted is only meaningful beside not-X is rejected with this specific error. |
| 5 · Assert zero where the design claims free. | Silent cost. Where the cascade claims to reject before spending, the test asserts the call counter and the run counter are both zero — not that the result was a rejection. |
| 6 · No try/except around the assertion. | A stub raising NotImplementedError being caught and read as a pass. If a test needs a broad except, the test is wrong. |
| 7 · Determinism is asserted, not assumed. | Replay drift. Any function claimed to be a pure fold gets a test that runs it twice on the same events and compares byte for byte. |
| 8 · One golden run, compared whole. | Everything the unit tests miss. A single end-to-end fake run writes an event log that is diffed against a checked-in fixture. Every change that alters the loop’s behaviour must update that fixture deliberately, which makes accidental behaviour changes visible in review. |

> **THE SHORT-CIRCUIT THAT MATTERS MOST**

The tempting shortcut at hour twenty is to make the oracle path optional — a flag that skips it when the file is missing, so the run completes. Do not add that flag. If the oracle is unavailable the run should still complete, but claim_level() must return L4-m and the report must say so in its own words. The value of the whole exercise is that the claim tracks the evidence; a flag that lets a run finish quietly at the wrong rung destroys exactly the property being demonstrated.

## The fourteen steps  ·  _dependency order · ~14 h hands-on_

Ordered by what must be true for the next step to be checkable, which is not the same as ordered by size. Steps 1, 2, 3, 6 and 4 — in that order — make the measurement true. Steps 5 and 7 to 12 make the loop honest. Steps 13 and 14 spend the result. Execute 6 before 4 and 5: until the synthetic template is replaced no real candidate can run, so step 3’s gate stops at the scorer and step 6 owns the first end-to-end run.

---

### STEP 1 — Make one tree that is true
`~60 min | no dependencies | blocks everything`

**Current state**

- `[TREE]` HEAD is 3e22b28 on docs/phase-9-handoff. As of 30 Aug three pull requests are open: #17 docs, #16 phase-9 outputs, #13 the phase-6 runner and ladder fix. #11 was closed and #15 (app batches 2+3) merged on 29 Aug — substeps 1.1 and the #15 half of 1.3 are already done. Check with gh pr list --state open before acting.
- `[TREE]` The suite does not collect on a stale environment: pytest --co stops with Interrupted: 1 error during collection on tests/test_07_tuner.py. With --ignore tests/test_07_tuner.py it is 123 passed, 1 failed, 11 deselected in 761 s. The single failure is test_00_skeleton.py::test_every_module_imports, caused by harness/agents/tuner.py importing optuna, which is absent from the active environment — though optuna==4.9.* is declared in pyproject.toml. The environment is stale, not the manifest.

Why this is first

Every later step is judged by whether the suite went from green to red. With one pre-existing failure and five divergent branches you cannot tell your own breakage from inherited breakage, and within two hours you will be debugging someone else’s merge instead of building. This step buys the ability to be wrong cheaply for the rest of the run.

PR #13 is not housekeeping. It carries the per-rung score_split that step 4 depends on, which makes it the load-bearing merge of the whole plan.

**Substeps**

**1.1 — Close #11 without merging — already done, 29 Aug**

Skip if gh pr view 11 --json state says CLOSED. It conflicts and #15 supersedes it. Closing costs nothing and removes the one branch that will otherwise consume an hour of conflict resolution for zero new behaviour. Leave a one-line reason on the PR so the decision is legible later.

**1.2 — Merge #16 first, alone, and run the suite**

Not #13. #16 strictly contains #13 — its tip is an ancestor, and no commit in #13 is missing from #16. They touch the same nine files, so merging #13 first would apply the same work twice and conflict on every one of them. Merge #16 and #13 closes itself.

This is also the merge that matters most. On main, harness/outputs.py and harness/audit.py are entirely stubs — ten functions raising NotImplementedError, including the submission writer, the convergence rule and the report generator. #16 implements all of them and wires two into the tree: Convergence at tree.py:406 and write_submission at tree.py:722. It also carries the per-rung score_split that step 4 depends on.

**1.3 — Then #17 (#15 merged 29 Aug)**

Skip #15 if gh pr view 15 --json state says MERGED. Both are independent of #16 and of each other, touching only app/static/ and context/. No sequencing risk.

**1.4 — Sync the environment, then harden only if it is still red**

Because optuna is a declared dependency, the first move is python -m pip install -e . — the manifest is right and the virtualenv is behind it. Run the suite again before doing anything cleverer.

If it still fails, then harden: tuner.py is a phase-7 agent no path in the planned run uses, so move the import inside the function that needs it. Module discovery should not depend on a package only one code path wants. That is a small improvement, not the fix, and doing it first would have hidden a stale environment that will bite again in step 3.

```
# harness/agents/tuner.py — the hardening, ONLY if pip install -e . left it red
- import optuna
+ def _optuna():
+     import optuna          # imported at use, not at module load
+     return optuna
```

> **EXECUTE**

**EDIT** harness/agents/tuner.py only if the install does not fix it

```
git checkout main && git pull
# 30 Aug: #11 is already CLOSED and #15 already MERGED — the two lines that touch them are no-ops; keep them for the record
gh pr close 11 --comment "superseded by #15; conflicting and no unique behaviour"

# confirm the containment before trusting this order:
git fetch origin
git merge-base --is-ancestor origin/fix/phase-6-review origin/phase-9-outputs   && echo "#16 contains #13"          # expect this to print

# #16 alone, first. it brings #13's rung fix AND implements outputs.py + audit.py.
gh pr merge 16 --merge && git pull && pytest -q
gh pr view 13 --json state              # expect MERGED; if OPEN, close it

# then the two independent ones — disjoint paths, no sequencing risk
gh pr merge 15 --merge && gh pr merge 17 --merge
git pull

# optuna==4.9.* IS declared in pyproject — the failure is a stale environment,
# not a missing declaration. Sync first, and only harden if it still fails.
python -m pip install -e .
pytest -q
```

**Verify:** pytest -q | tail -1 reports 0 failed, gh pr list --state open prints nothing, and grep -rc NotImplementedError harness/outputs.py harness/audit.py reports 0 in both — that last one is how you know #16 really landed. If test_every_module_imports still fails after the install, make the optuna import lazy — move it inside the function that uses it — so module discovery never depends on an optional package.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_every_module_imports | Every module under harness/ imports with no optional dependency installed. | It walks the package rather than listing modules, so a new module is covered the day it is written. |
| test_tuner_import_is_lazy | Importing tuner with optuna absent from sys.modules succeeds; calling the tuner then raises a clear error. | The refusal twin. A lazy import that silently no-ops would pass the first half alone. |

**GATE:**
pytest -q ends 124 passed, 0 failed, gh pr list --state open returns empty, and git log --oneline -1 on main is a merge you made.

**If you drift here**

Symptom: a merge conflict in runner.py or tree.py you cannot resolve confidently. Do not guess. Both files are described line by line in steps 4, 10 and 11 of this document — read the relevant step, then resolve in favour of the behaviour described there.

Symptom: the suite takes 12 minutes and you are iterating. Use pytest -q -x --ff to run last-failed first, and reserve the full run for the gate.

---

### STEP 2 — Get ground truth on disk
`~60 min | needs step 1 | everything numeric depends on it`

**Current state**

- `[TREE]` The dataset is not on disk and the word KuaiRand appears nowhere in the repository. data/ is a Python package — ingest.py and schema.py — and both are stubs raising NotImplementedError, written for Ali-CCP.
- `[PAGE]` The task is within-user ranking on long_view over KuaiRand-Pure. The external oracle is log_random_4_22_to_5_08_pure.csv, roughly 1.18 M randomly-exposed impressions across 0422–0508 — free of the logging policy’s bias because exposure was random rather than chosen by a recommender. Only the 0422–0428 rows are used (measure the count); the rest fall in the hidden test window.
- `[PAGE]` User composition on the test split (baseline_scores.json): 27.1% of users have no positive at all, 9.2% are all-positive. Together 36.3% can form no valid ranking pair. Train and valid are not published and must be measured separately — they will differ, and that is not an error. This number decides the design of step 10 and should be the first thing you re-verify.

Why before the task adapter

The adapter’s shape is decided by the columns that actually exist, and every calibration constant in step 5 is a property of the real data. Writing the adapter against a remembered schema and then meeting the file is how you end up with an adapter that reads plausibly and scores nothing.

The random-exposure log is the entire reason this project can claim L4-v rather than L4-m. It is a split whose contents the search cannot influence, which is what AIRA-2 (arXiv:2603.26499) means by decoupling the signal that steers from the signal that selects. Download it in the same breath as the training data; a run that reaches step 13 without it has to downgrade its own claim.

**Substeps**

**2.1 — Fetch KuaiRand-Pure and record the digest of every file**

Write the SHA-256 of each raw file into protocols/kuairand.yaml as you go. The protocol layer already verifies digests at prepare() time — synthetic.py:205 compares computed digests against ruler["data"][...]["sha256"] and refuses placeholder values. That machinery is free and it is what makes “we did not change the data mid-run” checkable rather than promised.

**2.2 — Verify the composition numbers yourself before trusting them**

Count users with zero positives, users with all positives, and the resulting fraction that can form no pair — for train and valid, the splits you may open — and write them into the protocol file keyed by split. The published 27.1 / 9.2 / 36.3 are test figures: copy them from baseline_scores.json, never recount them, because counting means reading test labels. Expect valid and train to differ from test; that is not an error. Step 10’s pair-count observable is designed around the test figure.

**2.3 — Write the candidate-visible files and the harness-only files — as CSV, from the kit’s own splits**

Follow the convention synthetic.py already establishes: candidate-visible files at the workspace root, everything else under harness_only/. That directory name is the enforcement boundary and it should stay that way. The files are CSV with a row_id column, not parquet — the kit is numpy over CSV and the candidate (step 6) will be too.

```
root/train.csv                  # candidate sees — data.load()["train"], 0408–0421
root/search_validation.csv      # candidate sees — data.load()["valid"], 0422–0428
root/oracle_features.csv        # candidate sees — the random log, 0422–0428 ONLY, FEATURES ONLY, long_view stripped
root/harness_only/search_labels.csv       # row_id, user_id, video_id, long_view for valid
root/harness_only/oracle_labels.csv       # same four columns for the random log; joined after predictions
root/harness_only/test_features.csv       # data.load()["test"], 0429–0508, FEATURES ONLY — read once, by the final submission run (3.5)
# no test LABEL is written anywhere. test features sit under harness_only/ and reach a candidate exactly once.
```

**2.4 — Do not reimplement the split — it is temporal, and it is the kit’s**

data.py defines SPLITS by date: train 20220408–20220421, valid 20220422–20220428, test 20220429–20220508. Wrap data.load and data.encode; do not write a splitter. A user-carved random split scores a different population from the leaderboard, and it destroys row_id, which submit.py --check defines as the index into data.load()[split] in file order — sort anything and every submission is rejected. The holdout is not a carved slice either: TaskPaths.holdout_validation binds to log_random_4_22_to_5_08_pure.csv, the random-exposure log, which is independent of the search by construction rather than by shuffling.

> **EXECUTE**

**NEW** data/kuairand.py thin wrapper over the kit’s data.load / data.encode, CSV writer, digest writer
**NEW** protocols/kuairand.yaml copy the shape of protocols/aliccp.yaml
**NEW** tests/test_09_kuairand_data.py

```
# 1 — download (Zenodo direct link, no registration) and reproduce the kit's two anchors
cd ~/Downloads/kuairand-starter-kit
wget https://zenodo.org/records/10439422/files/KuaiRand-Pure.tar.gz
tar xzf KuaiRand-Pure.tar.gz                    # → ./KuaiRand-Pure/data/
python3 baseline.py --model random              # test 0.4753 ± 0.001 — the kit's self-check
python3 baseline.py --model fm                  # test 0.5946 · valid 0.6016 · ~40 s
#   random missing 0.475 by more than 0.001 means the kit's harness is broken — STOP.
#   this is the kit scoring its own test split, once. the harness never does.

# 2 — point the harness at the raw files. the oracle is log_random_4_22_to_5_08_pure.csv.
ln -s ~/Downloads/kuairand-starter-kit/KuaiRand-Pure/data data/raw
ls -la data/raw/ && shasum -a 256 data/raw/*.csv

python -m data.kuairand build --raw data/raw --out data/kuairand
```

```
# data/kuairand.py — the two decisions that are hard to reverse

# 1. the split is the KIT's, temporal, in file order. never shuffle, never sort:
#    row_id = position in data.load()[split], and submit.py --check checks it.
import sys; sys.path.insert(0, str(KIT_DIR))          # ~/Downloads/kuairand-starter-kit
from data import load, encode, SPLITS, LABEL           # SPLITS is by date; LABEL == "long_view"
splits = load(raw_dir)                                 # {"train","valid","test"} — test is loaded, never written
write_csv(out / "train.csv",             rows=splits["train"], with_label=True)
write_csv(out / "search_validation.csv", rows=splits["valid"], with_label=False)
write_csv(out / "harness_only" / "search_labels.csv", rows=splits["valid"], labels_only=True)
write_csv(out / "harness_only" / "test_features.csv",  rows=splits["test"],  with_label=False)   # the submission must score these rows

# 2. the oracle is written TWICE: features where the candidate can read them,
#    labels under harness_only/ where it cannot. long_view is the ONLY label
#    the kit scores; strip every label column regardless.
LABELS = ["is_click", "long_view", "is_like", "is_follow", "is_comment", "is_forward", "is_hate", "play_time_ms"]
oracle = read_random_log(raw_dir / "log_random_4_22_to_5_08_pure.csv")   # file order kept
oracle = [r for r in oracle if 20220422 <= r.date <= 20220428]         # VALID's window ONLY. the raw log runs to 0508 and
#    overlaps the hidden test window; keeping those rows contradicts "no test-dated row is
#    candidate-visible" (the test two tables down). README direction 7 sanctions the file;
#    the date filter keeps the claim clean. re-assign row_id AFTER the filter, 0-based.
write_csv(out / "oracle_features.csv", rows=oracle, drop=LABELS)          # candidate sees
write_csv(out / "harness_only" / "oracle_labels.csv", rows=oracle,
          keep=["row_id", "user_id", "video_id", "long_view"])            # harness only

# every candidate-visible CSV carries row_id as its first column, 0-based, contiguous.
# then write every sha256 into protocols/kuairand.yaml — prepare() verifies them
```

**Verify:** head -1 data/kuairand/oracle_features.csv starts with row_id, and contains no long_view, is_click or any other label column; grep -l 202204[23][0-9]\|202205 data/kuairand/*.csv finds test-dated rows in no candidate-visible file. Then compute the composition on valid from harness_only/search_labels.csv (users with no positive, users with all positives, the remainder) and write it into the protocol. Take the test figures (27.1 / 9.2 / 36.3) from baseline_scores.json, not from the data — baseline.py does not print them, and counting them yourself means reading test labels. Valid’s figures will not match test’s, and should not.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_digests_match_protocol | Every file’s computed SHA-256 equals the value in kuairand.yaml. | Recomputed from bytes on disk at test time; a stale protocol fails immediately. |
| test_no_placeholder_digests | No digest in the protocol is a placeholder value. | The refusal twin for the above — otherwise a file of zeros would “match”. |
| ⚠ fails today · test_oracle_features_have_no_label | The candidate-visible oracle file contains no label column, under any spelling. | It checks the file rather than the loading code, so no code path can restore the column. |
| test_splits_are_the_kits | Every row of train.csv is dated 0408–0421, every row of search_validation.csv 0422–0428, and row_id in each equals its index in data.load()[split]. | Computed from the files against the kit’s own load(), so a re-implemented or re-ordered split cannot hide behind plausible-looking files. |
| test_no_test_dated_row_is_candidate_visible | No file outside harness_only/ contains a row dated 0429–0508, and no file anywhere carries a test label — test_features.csv has no long_view column. | Structural enforcement of the “never open the test log” rule — a path the candidate never receives beats a rule it could break. |
| test_composition_matches_protocol | The recorded no-positive and all-positive fractions match the data, per split; the test-split pair equals the figures in baseline_scores.json (27.1 / 9.2) — the only place they may come from. | Pins the number step 10 is designed around, so a data change that invalidates the design fails loudly here rather than silently there. |

**GATE:**
The kit’s two anchors reproduce (--model random within 0.001 of 0.4753, --model fm near 0.5946 — run by the kit, on its own test split, once). Five files on disk, five digests in the protocol, and pytest -q tests/test_09_kuairand_data.py green — including the oracle-label test, which must fail if you deliberately add a label column back and pass once you remove it. Try that both ways before believing it.

**If you drift here**

Symptom: the download is slow or unavailable and you are tempted to proceed with a subsample. A subsample is fine for building the adapter and calibration is not — σ is a property of the full data and every threshold in step 5 derives from it. Note in the protocol that calibration used a subsample and re-run step 5 when the full file lands.

Symptom: you cannot get the random-exposure log. Continue through step 13, but do not remove the oracle code path. Let claim_level() return L4-m and let the write-up say why. That is a weaker result and an intact argument.

---

### STEP 3 — Re-point the task layer
`~120 min | needs step 2 | largest single build`

**Current state**

- `[TREE]` Two adapters exist. synthetic.py is 313 lines and fully working. aliccp.py is a stub — every one of its four methods raises NotImplementedError.
- `[TREE]` The interface is four methods on tasks/base.py: prepare, candidate_env, score(preds, split), rows(split). TaskPaths already carries a holdout_validation field — the seat for the oracle exists.
- `[TREE]` measure.py:45 sets METRIC = "cvr_auc", a global constant naming the Ali-CCP metric. Every verdict, band and ladder comparison reads it.
- `[PAGE]` The KuaiRand metric is primary = mean(GAUC, nDCG@5), defined by the kit’s evaluate.py and nowhere else. Reference points on valid — the only split the harness ever scores: random 0.4834, item-popularity 0.5807, FM baseline 0.6016 — the bar — and an oracle ceiling of 0.8484. The test-split numbers (0.4753 / 0.5715 / 0.5946 / 0.8645) are the leaderboard’s and the kit checks them itself in step 2; the harness must never produce them.

> **DO NOT PORT ALICCP.PY**

It is the natural thing to open and it will cost you an hour. It contains no implementation to adapt — only the method signatures, which you already have from base.py. Copy synthetic.py instead. It is the only adapter that has ever produced a number, and it encodes several decisions worth inheriting: the harness_only/ boundary, digest verification against the protocol, and — most valuably — a score() that refuses to proceed unless the prediction file’s id set exactly equals the label set. Two things do not come along: the parquet writing (store_schema=False, pyarrow) — the kit is numpy over CSV — and the id column, which becomes row_id.

Why the row_id check matters more than it looks

That equality check at synthetic.py:277 is what makes the oracle path safe in step 4. When the candidate is handed oracle features, it must emit predictions for every oracle row; if it emits a subset, the check fails loudly instead of quietly scoring a convenient slice. Inherit it exactly, re-keyed on row_id, and make it stricter than set equality: row_id must be 0-based and contiguous in file order, because that is what submit.read_submission demands and (user_id, video_id) is not unique — 3.06% of test rows are repeated pairs, one of them twelve times.

It is also the smallest working example of the numerical-honesty principle from AgentX (arXiv:2606.26859): the scoring layer will not accept a plausible-looking artefact, it verifies the artefact’s shape and then computes the number itself.

**Substeps**

**3.1 — Write protocols/kuairand.yaml from the aliccp template**

Same shape: schema_version, task, ruler with data digests, splits, metrics, scoring, baseline, convergence, seeds. Fill the digests from step 2. Write convergence.epsilon: 0.002 and n_rounds: 3 now — they are the organisers’ numbers from baseline_scores.json, not measurements, and step 5 does not touch them. Splits are the kit’s date ranges; the metric block is primary over all impressions, positive long_view, output score. The complete file, key by key, is in “How the files wrap the task” above — keep the five digest key paths it marks, they are what prepare() and fake mode read. Leave only the calibration block (σ) null for step 5 — the loader treats a placeholder as an error, so a forgotten null fails at startup rather than mid-run. Then delete the Ali-CCP layer: data/ingest.py, data/schema.py, harness/tasks/aliccp.py, protocols/aliccp.yaml — six NotImplementedError go with them and nothing imports them — but two tests read protocols/aliccp.yaml (test_00_skeleton.py:225 for the nulls check, test_01_protocol.py:14 and :83 for load and task name): retarget both to synthetic.yaml in the same PR or the deletion turns the suite red.

**3.2 — Write harness/tasks/kuairand.py by copying the synthetic adapter**

Replace the generator with a wrapper over the kit’s data.load and data.encode (step 2’s data/kuairand.py). Keep the digest verification and the whole of score()’s validation preamble, re-keyed on row_id. Drop the parquet flags and the pyarrow import: CSV in, CSV out, numpy only.

**3.3 — Delegate the metric to evaluate.py — do not implement it**

Join predictions to the split’s labels by row_id, then call the kit’s evaluate(user_ids, labels, scores) unmodified and return its dict re-keyed as {"gauc", "ndcg_at_5", "primary"}. Returning the components is not decoration — step 10 attributes a pairwise-loss change by checking that GAUC moved more than nDCG@5, and it cannot do that if the adapter only returns the average.

The edge cases are already decided in evaluate.py’s header and you inherit them by not reimplementing: a zero-positive user scores nDCG 0.0 and is averaged in; GAUC counts only users with 0 < positives < impressions and is weighted by positive count, not a plain mean; nDCG gain is 2^rel − 1. A hand-rolled roc_auc_score loop with np.mean(gaucs) is a second definition of the score, and it is wrong. Pin the file: put evaluate.py’s SHA-256 in the protocol beside the data digests.

**3.4 — Make the metric name come from the task — do not rename the global**

Because step 6.0 keeps the synthetic task alive, cvr_auc stays in use at ~40 sites (synthetic.py, fake_run.py, six test files, the reducer tests). Renaming measure.METRIC to "primary" would break all of them. Instead each adapter declares metric: str — "cvr_auc" on SyntheticTask, "primary" on KuaiRandTask — and Measure takes it at construction; every site that read the module constant reads self.metric. Two hardcoded literals must go with it: measure.py:45 and agents/tuner.py:103 (result.metrics.get("cvr_auc", 0.0)). fake_run.py keeps cvr_auc — it is a synthetic fixture and its golden log must not change.

**3.5 — Retarget the submission read-back before it can bite you**

After step 1, outputs._readback_predictions exists and validates the submission file. It is inherited from Ali-CCP: it requires a p_conversion_given_click column, explicitly rejects p_click_and_conversion, and calls task.rows("test") — a split name the adapter’s rows() mapping does not carry.

Left alone, every one of those rejects a valid KuaiRand submission. Fix it here rather than in step 14, because the failure fires at the moment the submission is written — with the deadline in sight and nothing else left to try. PREDICTION_COLUMNS becomes (row_id, user_id, video_id, score); the [0,1] clamp at outputs.py:72 goes (score is any real, only its order matters); NaN and infinity are rejected. Then delegate the read-back body to the kit’s submit.read_submission(path, rows) so your definition of a valid submission cannot drift from the organisers’ — it needs a full data.load, so cache the split rather than reloading on every check. Keep the structure: write, read back, emit submission_written only if the read-back passes.

Where the test predictions come from. The candidate trains on TRAIN and scores whatever VALID points at. So write_submission re-runs the winning node’s template — same commit, same seed, therefore the same model — with VALID=harness_only/test_features.csv, then reads the file back through submit.read_submission(path, data.load()["test"]). That is the one time test-dated rows reach a candidate: features only, after convergence, recorded as a submission_run event with the node id and the digest of the file scored. The rules’ “validation-best checkpoint” is this node; retraining it deterministically is simpler than a predict-only entrypoint and yields the same numbers, which test_template_honours_seed in step 6 pins.

**3.6 — Register the adapter and record the three reference scores**

Score the random, item-popularity and FM predictors through score(preds, "search") — that is the valid split — and put the results in the protocol. If they land near 0.4834 / 0.5807 / 0.6016 the join and the delegation are right. Do not reach for 0.4753 / 0.5715 / 0.5946: those are test-split numbers, and the only way the harness can produce them is by scoring the split it must never open. This is the cheapest possible verification of the most load-bearing function in the repository, and it takes four minutes.

> **EXECUTE**

**NEW** harness/tasks/kuairand.py copy synthetic.py, replace generate() with a reader
**EDIT** harness/tasks/__init__.py register the adapter by name
**EDIT** harness/measure.py line 45 · METRIC becomes Measure(metric=task.metric); also agents/tuner.py:103
**EDIT** harness/tree.py construct Convergence(eps, n_rounds) from protocol.ruler["convergence"] — it counts rounds on the incumbent's valid primary, never on the oracle
**EDIT** harness/outputs.py PREDICTION_COLUMNS, drop the clamp, delegate read-back to submit.read_submission
**DEL** data/ingest.py · data/schema.py · harness/tasks/aliccp.py · protocols/aliccp.yaml the Ali-CCP layer, six NotImplementedError — and retarget test_00_skeleton.py:225, test_01_protocol.py:14/:83 to synthetic.yaml
**NEW** tests/test_10_kuairand_task.py

```
# harness/measure.py:45 — the constant becomes a constructor argument
- METRIC = "cvr_auc"
+ class Measure:
+     def __init__(self, ..., metric: str):   # task.metric — "cvr_auc" synthetic, "primary" kuairand
+         self.metric = metric
# harness/agents/tuner.py:103 — the other hardcoded literal
- return float(result.metrics.get("cvr_auc", 0.0))
+ return float(result.metrics.get(self.metric, 0.0))

# then the checklist: no metric literal may remain in the task-blind layer
grep -n '"cvr_auc"\|"primary"' harness/measure.py harness/tree.py harness/agents/tuner.py harness/runner.py   # must be empty
grep -rn 'aliccp' harness/ tests/ data/ protocols/    # must be empty after 3.1's deletions + the two test retargets
```

```
# harness/tasks/kuairand.py — the metric is NOT implemented here. it is delegated.
# evaluate.py is the definition of the score; its header freezes every convention
# (positive-weighted GAUC, zero-positive users → nDCG 0 and averaged in, 2^rel-1 gain).
from evaluate import evaluate            # the kit's, on sys.path via KIT_DIR — never copied, never edited

def score(self, preds_path, split) -> dict[str, float]:
    labels = self._labels(split)         # harness_only/{search,oracle}_labels.csv, file order
    preds  = _read_preds(preds_path)     # row_id, user_id, video_id, score
    # validation preamble — KEEP the discipline of synthetic.py:265-285, re-keyed:
    #   header == (row_id, user_id, video_id, score); row_id 0-based and contiguous;
    #   user_id/video_id align with labels row for row; score finite; count equal.
    #   this is exactly submit.read_submission's contract — reuse it, do not re-derive it.
    if len(preds) != len(labels) or (preds["row_id"] != np.arange(len(labels))).any():
        raise ValueError(f"row_id must be 0..{len(labels)-1} contiguous; got {len(preds)} rows")
    m = evaluate(labels["user_id"], labels["long_view"], preds["score"])   # unmodified
    return {"gauc": m["GAUC"], "ndcg_at_5": m["nDCG@5"], "primary": m["primary"]}

# return the COMPONENTS, not just the mean: step 10 attributes a pairwise
# change by comparing gauc movement to ndcg movement.
```

**Verify:** score three reference predictors through score(preds, "search") on valid: random → ~0.4834, item popularity → ~0.5807, FM → ~0.6016. All three within tolerance means the join by row_id is right; one off means you joined on (user_id, video_id), sorted something, or scored the wrong split. Then python3 ~/Downloads/kuairand-starter-kit/submit.py --check --split valid <preds.csv> accepts the FM file. The end-to-end run-one check belongs to step 6 — today’s template is the synthetic torch script and cannot read these files.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_random_predictor_scores_near_half | A random-score submission on valid lands within tolerance of 0.4834. | An implementation that ignores the labels cannot hit a specific non-trivial value; it would land at 0.5 or crash. |
| test_popularity_beats_random | Item-popularity scores above random and below FM on valid (0.4834 < 0.5807 < 0.6016). | Pins the ordering of three independent predictors — no single-constant bug survives all three. |
| test_score_delegates_to_kit_evaluate | evaluate.py’s SHA-256 equals the protocol’s, and score() calls it (spy on evaluate; a hand-rolled metric leaves the spy uncalled). | A second definition of the score cannot exist if the only one is pinned by digest and observed by call. |
| test_harness_never_scores_test | score(preds, "test") raises; no label file for test exists under harness_only/. | The one thing the harness must never do is made impossible by absence, not by discipline. |
| test_score_rejects_missing_ids | A prediction file missing rows raises, naming the count difference. | Refusal twin; this is the guard that makes the oracle path safe. |
| test_score_rejects_noncontiguous_row_id | A duplicated or skipped row_id raises, and so does a file sorted by score. | The other way to satisfy a set-equality check while being wrong — and the exact rejection submit.py --check would give later. |
| test_metric_returns_components | score() returns gauc and ndcg_at_5 alongside primary. | Step 10 imports these keys; without the test they get quietly dropped in a refactor and attribution silently degrades. |
| test_metric_name_comes_from_task | No metric literal ("cvr_auc" or "primary") appears in measure.py, tree.py, tuner.py or runner.py; Measure(metric="primary") and Measure(metric="cvr_auc") both produce verdicts on their own task’s metrics dict. | A grep over the task-blind layer plus the affirmative twin on both tasks. Catches the literal you missed in 3.4 and keeps the synthetic suite green. |

**GATE:**
Three reference predictors score within tolerance of their published valid values through score(preds, "search"), the kit’s FM prediction file passes submit.py --check --split valid, and pytest -q tests/test_10_kuairand_task.py is green. The first end-to-end run-one is step 6’s gate. (There is no --task or --rung flag on the CLI; the four subcommands are in “Conventions”.)

**If you drift here**

Symptom: your FM baseline scores far from 0.6016. You cannot have broken the metric — you did not write it — so check the join: row_id order lost, a merge on (user_id, video_id) that duplicated the 3% repeated pairs, or the test split scored by mistake (which lands you near 0.5946 and is worse than a wrong number). Print the row count against len(data.load()["valid"]) = 124,909 before anything else.

Symptom: you are three hours in. The metric is the part that must be right; the ingest path is the part that must merely work. If you are over time, hardcode a simple loader and keep the metric careful.

---

### STEP 4 — Make the instrument honest
`~75 min | needs steps 3 and 6 | the L4-v claim lives here`

**Current state · three defects, all previously identified**

- `[TREE]` The holdout rung does not score the holdout. runner.py:390 passes the literal string "search" to task.score for every rung, so the holdout rung measures the search split and reports it as a holdout number. PR #13 introduces a per-rung score_split and fixes this — which is why that merge was step 1.2.
- `[TREE]` The capability wall blocks the oracle. runner.py:547 asserts set(task.candidate_env(paths)) <= {"TRAIN", "VALID"}. The candidate therefore never receives the oracle rows and emits no predictions for them, so scoring them is impossible — the oracle is not one extra call, it needs a third path.
- `[TREE]` The visit cap contradicts the policy, in two places. measure.py:33 sets HOLDOUT_VISITS_MAX = 2 while the design gates every promotion — and tree.py:592 enforces the same budget with a hardcoded literal 2 rather than the constant. Changing only the constant leaves the tree still stopping at two visits, silently.
- `[TREE]` Holdout is not a ladder rung, by design. measure.py:349 raises RungMismatch("holdout is not a ladder rung; use holdout_report()"). That separate path already owns the seed set, the visit counting and the budget exception, so the oracle reuses it rather than becoming a new entry in RUNG_SPECS.

The reasoning, so you can defend the change

Widening a capability wall is the kind of edit that should make you uncomfortable, and the discomfort is correct. The resolution is not to trust the candidate more; it is to make the new path safe by construction. The oracle file the candidate sees has no label column at all — the labels stay in harness_only/ and are joined after predictions are written. So even a candidate that tried to cheat has nothing to read.

On the visit cap: Dwork and colleagues (arXiv:1411.2664) show that a holdout consulted repeatedly, with each answer shaping the next question, stops being held out. That is a real constraint and the reason a cap exists. But the bound is about the number of adaptive queries, not about the number two — and the count is exactly what we should be reporting rather than minimising. Raise the cap, keep the event, print the total.

**Substeps**

**4.1 — Confirm PR #13’s rung specs landed**

After step 1, RUNG_SPECS should carry score_split per rung — None for smoke, "search" for screen, full and replicate, "holdout" for holdout — and line 416 should read self.task.score(preds, spec.score_split). If it does not, the merge did not include what you think it did.

**4.2 — Widen the wall by exactly one name**

```
# harness/runner.py — capability wall
env.pop("HOLDOUT", None)
- assert set(task.candidate_env(paths)) <= {"TRAIN", "VALID"}
+ assert set(task.candidate_env(paths)) <= {"TRAIN", "VALID", "ORACLE"}
# ORACLE points at oracle_features.csv. Labels never leave harness_only/.
```

One name, not a wildcard. The test in step 4’s table asserts that a fourth name is still rejected, because a wall widened by one is only still a wall if it refuses the second one.

**4.3 — Bind the oracle to the holdout slot and raise the cap in the one place it lives**

The oracle is not a new rung: TaskPaths.holdout_validation already binds to the random-exposure log and holdout_report() already owns the seed set, the visit counting and HoldoutBudgetExceeded. Set HOLDOUT_VISITS_MAX = 12 — every promotion plus headroom for a run that goes better than expected — and delete the duplicate private-counter check at tree.py:592 so the rule lives only at measure.py:460. Keep the exception, keep the per-visit event. The cap is now a tripwire against a runaway loop rather than a budget you are rationing.

**4.4 — Write both numbers into one event**

A promotion emits its validation delta and its oracle delta in the same record. Not two events joined later — one event. Step 12’s monitors are folds over this field, and a fold that has to join two event streams by node id is a fold that will one day silently drop a promotion.

> **EXECUTE**

**EDIT** harness/runner.py the capability wall, ~line 547
**EDIT** harness/measure.py line 33 · HOLDOUT_VISITS_MAX
**EDIT** harness/tasks/kuairand.py candidate_env gains ORACLE on the oracle rung
**NEW** tests/test_11_eval_integrity.py

```
# 1 — confirm PR #16 landed the rung specs (it carries #13's fix)
grep -n 'score_split' harness/runner.py
#   expect RUNG_SPECS with score_split per rung, and
#   metrics = self.task.score(preds, spec.score_split)   — NOT the literal "search"

# 2 — the oracle is NOT a new rung. measure.py:349 raises RungMismatch:
#   "holdout is not a ladder rung; use holdout_report()". Reuse that path —
#   it already owns the seed policy, the visit counting and the budget exception.
grep -n 'holdout_report\|RungMismatch' harness/measure.py

# 3 — widen the wall by exactly one name
- assert set(self.task.candidate_env(paths)) <= {"TRAIN", "VALID"}
+ assert set(self.task.candidate_env(paths)) <= {"TRAIN", "VALID", "ORACLE"}

# 4 — the budget is enforced in TWO places. changing the constant is not enough.
#     measure.py:33
- HOLDOUT_VISITS_MAX = 2
+ HOLDOUT_VISITS_MAX = 12   # every promotion plus headroom; still a tripwire
#     tree.py:592 — a hardcoded literal, NOT the constant. this is the one
#     that would silently stop the oracle after the second promotion.
#     DELETE it (do not repoint it): measure.py:460 already raises
#     HoldoutBudgetExceeded, and one enforcement point cannot drift from itself.
- if self.measure._holdout_visits >= 2:
-     ...
```

```
# 5 — the type chain. the oracle IS the holdout slot (audit E), so the Rung
#     literal and Task.score's split Literal do NOT change. three edits, and
#     missing any one of them breaks the Protocol and fails the whole suite.
harness/types.py:21      Rung                      unchanged — "holdout" already exists
harness/tasks/base.py    Task.score(preds, split)  unchanged — Literal["search","holdout"]
harness/tasks/base.py    TaskPaths                 += oracle_features: Path | None
harness/tasks/*.py       candidate_env(paths, *, rung="screen")
harness/runner.py        the wall (item 3 above)
#     synthetic.py must stay conformant — accept rung=, return no ORACLE key.

# harness/tasks/kuairand.py — ORACLE points at FEATURES. labels stay behind.
def candidate_env(self, paths, *, rung="screen") -> dict:
    env = {"TRAIN": str(paths.train), "VALID": str(paths.search_validation)}
    if rung == "holdout":
        env["ORACLE"] = str(paths.oracle_features)   # oracle_features.csv — no label column exists
    return env

# TRAP: _build_env drops any variable whose VALUE contains "holdout",
# "rulebook" or "protocols/". Keep the oracle features OUT of harness_only/
# or the variable vanishes and you get a confusing KeyError in the candidate.
```

```
# 6 — one event, both numbers. not two events joined later.
events.emit("verdict", producer="measure", node=node.id, state="promoted",
            delta_mean=val_delta, oracle_delta=orc_delta, ...)
```

**Verify:** grep -n 'score(preds, "search")' harness/runner.py returns nothing; python -m harness fake --instant produces at least one verdict event carrying both delta_mean and oracle_delta; and deleting oracle_features.csv makes a real run fail with a named error rather than completing quietly. Also grep -n "_holdout_visits >= " harness/tree.py returns nothing.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| ⚠ fails today · test_holdout_rung_scores_holdout | The holdout rung’s number differs from the search rung’s on data constructed so the two splits disagree. | Fails on the pre-#13 tree. The fixture is built so a hardcoded "search" produces a specific wrong value — the test names the value it must not be. |
| test_candidate_env_allowlist | A task returning a fourth env name raises. | Refusal twin for 4.2. Without it, the widening reads as a licence. |
| ⚠ fails today · test_oracle_labels_never_in_candidate_env | No path in candidate_env resolves inside harness_only/. | Resolves paths on disk rather than comparing strings, so a relative path or symlink cannot slip past. |
| test_every_oracle_visit_emits_an_event | Visit count folded from the log equals the number of oracle scorings. | The adaptivity budget becomes auditable rather than remembered; it is also the number the write-up quotes. |
| test_oracle_budget_raises | Exceeding the cap raises HoldoutBudgetExceeded from measure.py, and tree.py contains no comparison against _holdout_visits. | Refusal twin. A cap that only logs is not a cap; a cap enforced twice will one day be enforced at two different numbers. |
| test_promotion_event_carries_both_deltas | Every promoted verdict has both fields populated, never one. | Step 12 depends on it; a partial event would make the monitor silently compute over a subset. |

**GATE:**
A fake run produces at least one promotion whose event contains both deltas, and deleting the oracle file makes that run fail with a clear message rather than completing quietly.

**If you drift here**

Symptom: the candidate crashes when handed the oracle path. Almost always the prediction file no longer covers every row_id of the oracle, because the candidate wrote predictions for validation only. That is the step-3 equality check doing its job — fix the candidate, do not relax the check.

Symptom: you are tempted to add a --skip-oracle flag to get a run through. Read the closing callout in the doctrine section above. Add the downgrade, not the flag.

---

### STEP 5 — Recalibrate the ladder
`~45 min | needs steps 4 and 6 | mostly waiting`

**Current state**

- `[TREE]` Every threshold in measure.py was tuned for a different task on different hardware: SCREEN_REJECT_DELTA = -0.010, SCREEN_ADVANCE_SD = 1.0, PROMOTE_FLOOR = 0.010, LADDER_ETA = 0.005, REPLICATE_K = 3, SIGMA_UNSTABLE = 0.020.
- `[PAGE]` On this task σ is about 0.0008 across five seeds, and the organizers’ convergence rule is ε = 0.002 over N = 3 rounds.
- `[TODO]` Your own σ, measured on your own metric implementation and your own machine. Do not inherit the number — measure it.

Why every constant is currently wrong by an order of magnitude

PROMOTE_FLOOR = 0.010 against a noise floor of 0.0008 means the bar sits at roughly twelve standard deviations. Nothing would ever be promoted; the run would look calm and converge on the baseline. Meanwhile SIGMA_UNSTABLE = 0.020 means the instability alarm would never fire either. The ladder is not broken, it is calibrated to a task where a point of AUC was a normal move.

LADDER_ETA = 0.005 deserves its own sentence, because it is the mechanism from Blum and Hardt’s Ladder (arXiv:1502.04585): report an improvement only when it exceeds a threshold, otherwise repeat the previous best. Withholding small movements is what stops a sequence of lucky readings from being climbed. You are not inventing this constant, you are re-deriving a published defence for a new noise level — and the count of accepted steps becomes the adaptive-query number step 12 reports.

**Substeps**

**5.1 — Measure σ with five seeds of the unchanged baseline**

Five screen-rung runs, no code changes between them, standard deviation of the primary metric. At roughly forty seconds each this is under four minutes of compute and it is the single most important number you will produce today, because every threshold below is a multiple of it.

**5.2 — Derive the thresholds from σ rather than choosing them**

```
SIGMA_UNSTABLE      = 6 * sigma      # a run this noisy is not measuring anything
SCREEN_REJECT_DELTA = -2 * sigma     # clearly worse, stop early
PROMOTE_FLOOR       = 2 * sigma      # just under eps — anything the organisers call a win clears it
LADDER_ETA          = EPS            # = 0.002. the Ladder threshold IS the organisers' eps, not 2.5σ of it
# eps = 0.002 and N = 3 come from the organisers and are NOT ours to tune.
```

Write the multipliers into the code as multipliers, with σ loaded from the protocol; write LADDER_ETA as the protocol’s ε, not as a multiple of σ — ε is given and σ is measured, and the one threshold that decides what counts as an improvement should be the one the organisers defined. A future reader then sees the reasoning rather than six unexplained decimals, and a change of hardware requires re-measuring one number instead of six.

**5.3 — Record σ, the multipliers and the resulting thresholds in the protocol**

Along with the date and the machine. The protocol hash changes, which is correct — a run under different thresholds is a different experiment and the log should say so.

> **EXECUTE**

**EDIT** harness/measure.py lines 15–31 · six constants become expressions
**EDIT** protocols/kuairand.yaml record sigma, the multipliers, the date, the machine
**NEW** tests/test_12_calibration.py

```
# 1 — five identical runs of the unchanged baseline. under four minutes total.
for s in 1 2 3 4 5; do
  python -m harness run-one --protocol protocols/kuairand.yaml --seed $s \
    | tee runs/calib-$s.json
done

# 2 — sigma is the standard deviation of primary across those five
python - <<'PY'
import json, statistics, glob
xs = [json.load(open(f))["metrics"]["primary"] for f in sorted(glob.glob("runs/calib-*.json"))]
print("scores:", xs)
print("sigma :", statistics.stdev(xs))
PY
```

```
# harness/measure.py — write MULTIPLIERS, not decimals, and load sigma from
# the protocol. a change of machine then means re-measuring one number, not six.
SIGMA = protocol.ruler["calibration"]["sigma"]        # measured above

EPS   = protocol.ruler["convergence"]["epsilon"]      # 0.002, organisers' — written in step 3.1

SIGMA_UNSTABLE      = 6.0 * SIGMA   # a run this noisy is not measuring anything
SCREEN_REJECT_DELTA = -2.0 * SIGMA  # clearly worse, stop early
PROMOTE_FLOOR       = 2.0 * SIGMA   # just under eps; a real win always clears it
LADDER_ETA          = EPS           # the Blum-Hardt threshold, pinned to the organisers' eps

# eps = 0.002 and N = 3 come from the organisers. NOT ours to tune, and
# test_epsilon_and_n_are_not_derived exists to keep it that way.
```

**Verify:** the printed sigma is near 0.0008. Above ~0.005 means something is non-deterministic that should not be — check that SEED reaches shuffling, initialisation and dropout before touching any threshold. Then confirm no bare decimal remains: grep -n 'PROMOTE_FLOOR\|LADDER_ETA\|SIGMA_UNSTABLE' harness/measure.py shows expressions, not literals.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_thresholds_derive_from_sigma | Each σ-derived constant equals its multiplier times the protocol’s σ, and LADDER_ETA equals the protocol’s ε exactly. | Recomputed from the protocol at test time, so a hand-edited constant fails — and so does an η quietly re-derived from σ. |
| test_epsilon_and_n_are_not_derived | ε and N come from the protocol’s organiser block and no code path scales them. | The refusal twin, and it guards the one thing we are genuinely not allowed to tune. |
| test_noise_sized_delta_does_not_promote | A synthetic delta of exactly 1σ fails to promote. | Tests the ladder’s purpose directly rather than its arithmetic. |
| test_real_delta_promotes | A delta of 4σ promotes. | Affirmative twin — a ladder that rejects everything would otherwise pass the test above. |

**GATE:**
σ is in the protocol, every threshold is an expression over σ or ε rather than a literal, and the two paired ladder tests pass together.

**If you drift here**

Symptom: σ comes out much larger than 0.0008, say above 0.005. Something is non-deterministic that should not be — check that the seed reaches data shuffling, initialisation and any dropout, and that the candidate honours SEED from the environment. Rule C4 in the constraints file exists for exactly this and is enforced from step 7 onward.

Symptom: nothing ever promotes in step 13. Come back here first. It is far more often a threshold left at 0.010 than a search that found nothing.

---

### STEP 6 — Rebuild the candidate and retarget the rules
`~60 min | needs step 3 | do before 4 and 5`

**Current state**

- `[TREE]` candidate/template.py is the synthetic candidate (Ali-CCP-shaped): a torch MLP, parquet in and out, sample_id keys, five fixed columns, two heads p_click and p_conversion_given_click, and a SYNTHETIC_FAIL switch the failure tests use. report.py is task-neutral and stays. Three test files run this template against synthetic data — test_03_template.py, test_03_synthetic.py, test_07_agents.py — so overwriting it in place turns the suite red and breaks the definition of done.
- `[TREE]` candidate/rules.jsonl holds seven constraints. C3 requires the literal string p_conversion_given_click, which no valid KuaiRand candidate contains. The moment step 7 wires the file up, C3 rejects every candidate on iteration one.
- `[PAGE]` Training a candidate takes roughly 40 s on one CPU core, numpy only. That figure is the economic premise of the entire design, so if a real run takes four minutes the round policy in step 11 needs revisiting.

Why the rules move with the task

Four of the seven constraints are task-independent and survive unchanged: honour the seed, call report.progress, checkpoint, no self-label features. Three are Ali-CCP specific — and the dangerous one is not C3, which trips loudly, but C1, whose forbid pattern names click|conversion and so is inert on a task whose label is long_view: a candidate reading validation labels would trip nothing. Keeping a stale rule is worse than having no rule, because a constraint that always trips teaches the loop that the constraint layer is noise — and the first thing a frustrated operator does is disable it.

The two rules marked "check": "llm" with a null pattern are not incomplete. They are the semantic level of NOVA’s cascade (arXiv:2606.27243), declared and waiting for the evaluator you build in step 7.

**Substeps**

**6.0 — One candidate per task — move, do not overwrite**

git mv candidate/template.py candidate/synthetic/template.py, write the KuaiRand script at candidate/kuairand/template.py, keep the one shared candidate/report.py. Give the task the say: add a candidate_dir: Path class attribute to each adapter (declare it on tasks/base.py) and make runner._stage_candidate copy from task.candidate_dir when run_cfg["candidate_src"] is unset, instead of the module constant CANDIDATE_DIR. The synthetic tests keep passing, the phase-6 patches in hypotheses/patches/ keep applying (they name template.py inside the git workspace), and the full suite stays reachable. Everywhere else on this page, candidate/template.py means the KuaiRand one from here on.

The spec is copied by hand in three places and they move together: protocols/kuairand.yaml → metrics.primary.output declares the column, rules.jsonl C3 demands it by regex, the template writes it. Nothing derives one from another; the tests in this step are the only thing that notices drift.

**6.1 — Rewrite the template to emit one score column**

Ranking, not a funnel: row_id, user_id, video_id, score as CSV, in the row order of VALID (or ORACLE), numpy and the csv module only — the 251 lines of torch, pyarrow and partitioned parquet go, and with them the two-minute collection tax on every pytest. Keep the harness-facing contract intact — report.progress on every epoch and report.checkpoint.save — because the stall watchdog and the resume path both depend on them, and rules C5 and C6 enforce them.

**6.2 — Retarget C1, C2 and C3; keep C4–C7; add C8 and C9**

```
- C1  forbid   VALID.*(click|conversion)      # inert: the label here is long_view
+ C1  forbid   VALID.*long_view               # no reading validation labels
- C2  (population clause names the Ali-CCP eval set)
+ C2  require  within-user ranking over each user's logged impressions — every VALID row scored
- C3  require  p_conversion_given_click       # Ali-CCP funnel head
+ C3  require  score                          # the ranking output column
+ C8  forbid   ORACLE.*(is_click|long_view)   # oracle features only, never labels
+ C9  forbid   log_standard_|log_random_|TEST # never open a raw kit log; only TRAIN/VALID/ORACLE paths
```

C8 is new and belongs to step 4’s widened wall. C9 is the belt on step 2’s braces: the test split is unreachable because no test-dated row is ever written where the candidate can read it, and C9 additionally forbids the raw files that contain it. The wall and the absent file are the structural defences; C8 and C9 are the cheap ones that catch the mistake before a run rather than during it.

**6.3 — Make the baseline candidate the FM model**

The incumbent at round zero should be the thing we must beat — the kit’s FM, 0.6016 on valid (0.5946 on the leaderboard) — not something weaker that makes early gains look impressive. Port baseline.py’s numpy FM (k=16, lr=0.001, batch 8192, patience 4) into the template rather than writing a new one. An inflated first delta is the fastest way to poison every comparison that follows, because everything is measured against the incumbent.

One thing does not port. The kit’s run_fm early-stops on valid labels (patience 4), which the candidate is forbidden to have. Train for a fixed epoch count instead — find it once with the kit, the epoch at which its early stop fires — or early-stop on a tail of TRAIN. Expect a small gap from 0.6016 and set test_baseline_reproduces_fm_score’s tolerance to ±0.003, not ±0.0008.

> **EXECUTE**

**EDIT** candidate/template.py → candidate/synthetic/template.py git mv; the synthetic tests keep their candidate
**NEW** candidate/kuairand/template.py the FM port: one ranking score column, numpy + csv
**EDIT** harness/tasks/base.py · harness/tasks/synthetic.py · harness/tasks/kuairand.py · harness/runner.py candidate_dir on the task; _stage_candidate reads it
**EDIT** candidate/rules.jsonl retarget C1, C2, C3; add C8, C9
**NEW** tests/test_13_candidate.py

```
# candidate/rules.jsonl — replace C1, C2, C3; append C8, C9. exact JSON, one per line.
- {"id":"C1", ... "pattern":"VALID.*(click|conversion)", ...}
+ {"id":"C1","statement":"Never reads validation labels.","check":"static","mode":"forbid","pattern":"VALID.*long_view","severity":"fail","source":"seed"}
- {"id":"C2", ... (Ali-CCP population clause) ...}
+ {"id":"C2","statement":"Scores every VALID row: within-user ranking over each user's logged impressions.","check":"llm","mode":"require","pattern":null,"severity":"fail","source":"seed"}
- {"id":"C3", ... "pattern":"p_conversion_given_click", ...}
+ {"id":"C3","statement":"Writes the ranking score column.","check":"static","mode":"require","pattern":"\"score\"","severity":"fail","source":"seed"}
+ {"id":"C8","statement":"Reads oracle features only, never oracle labels.","check":"static","mode":"forbid","pattern":"ORACLE.*(is_click|long_view|is_like)","severity":"fail","source":"seed"}
+ {"id":"C9","statement":"Never opens a raw kit log; reads only the TRAIN, VALID and ORACLE paths.","check":"static","mode":"forbid","pattern":"log_standard_|log_random_|\\bTEST\\b","severity":"fail","source":"seed"}

# the other four survive unchanged — they are task-independent:
#   C4 honour SEED/DEVICE   C5 report.progress   C6 checkpoint   C7 no self-label features

# step 13.1 additionally seeds three round-0 forbidden patterns from the organisers' dead ends.
```

```
# candidate/template.py — the harness-facing contract, unchanged in shape
train_path = Path(os.environ["TRAIN"])
valid_path = Path(os.environ["VALID"])
seed       = int(os.environ.get("SEED", "0"))       # C4

for epoch in range(epochs):
    ...
    report.progress(epoch, epochs, float(loss))      # C5 — every epoch
report.checkpoint.save(epoch, blob)                  # C6

# output: four columns, nothing else, in VALID's row order. numpy + csv, no pyarrow.
with open(workspace / "preds.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["row_id", "user_id", "video_id", "score"])
    for i, (u, v, s) in enumerate(zip(uids, vids, scores)):
        w.writerow([i, u, v, f"{float(s):.6g}"])      # row_id 0-based, contiguous
report.result({}, workspace / "preds.csv")           # harness scores it, not you
```

**Verify:** the shipped baseline is the FM model and scores near 0.6016 on valid — not something weaker, which would inflate every later delta. grep -n "import torch\|pyarrow" candidate/ returns nothing. Then python -m harness run-one --protocol protocols/kuairand.yaml --seed 1 twice at the same seed gives identical scores, and at different seeds gives different ones. Time one run: it should be near 40 s. If it is minutes, check dtypes on the user-id join before anything else.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| ⚠ fails today · test_every_require_rule_matches_the_template | Each require-mode pattern matches candidate/template.py. | Fails today because of C3. It is a general test, not a fix — the next time the task changes, this catches the stale rule automatically instead of after a wasted round. |
| test_template_emits_required_columns | A one-epoch run produces a CSV whose header is exactly row_id,user_id,video_id,score and which submit.read_submission accepts against the split. | Runs the template rather than reading it, and judges the output by the organisers’ reader rather than ours. |
| test_candidate_imports_no_torch | Neither torch nor pyarrow is importable from candidate/ code paths. | The 40-second premise and the test-collection time both depend on it; a stray import silently restores both costs. |
| test_template_honours_seed | Two runs at the same seed are identical; two at different seeds are not. | Both halves together. Determinism alone is satisfiable by ignoring the seed entirely. |
| test_baseline_reproduces_fm_score | The shipped baseline scores within tolerance of 0.6016 on valid. | Pins the incumbent at the number that matters, so a weak baseline cannot inflate every subsequent delta. |

**GATE:**
The baseline candidate trains, scores near the FM figure on valid, all nine rules match the template it produced, its output passes submit.py --check --split valid, and python -m harness run-one --protocol protocols/kuairand.yaml --rows 50000 --seed 1 completes end to end — the first real run of the whole pipeline. The synthetic tests are still green.

**If you drift here**

Symptom: a run takes minutes rather than seconds. Check row counts and dtypes first — a float64 join on a string user id will do this. The 40-second figure is a premise, not an aspiration; if it cannot be met, step 11’s policy of screening every survivor is the thing that has to give, and you should note that in the write-up rather than quietly screening one.

---

### STEP 7 — Wire the verification cascade
`~90 min | needs step 6 | defect · rules file has no reader`

**Current state**

- `[TREE]` candidate/rules.jsonl has no consumer. Grep the repository: the only reference is tests/test_03_synthetic.py:207, which parses it to confirm it is valid JSON. The constraint layer exists as a document and not as a mechanism.
- `[TREE]` A different constraint layer does run. harness/agents/contract.py enforces a hardcoded tuple of forbidden path fragments and five compiled leakage patterns, none of which the rules file knows about.
- `[TREE]` Level three of the cascade already exists as the smoke rung with SMOKE_TIMEOUT_S = 60.0. Level two does not exist at all.

What the cascade is for, in one paragraph

A generated change can be wrong in three ways that cost wildly different amounts to find. Breaking a stated rule is a pattern match. Being plausible but not actually implementing what it claims needs something that reads code — one model call. Being fine on both counts and still crashing on real data needs a run. NOVA orders these by cost so the expensive check only sees candidates that survived the cheap ones. The economic claim is testable and should be tested: when the first level trips, the model call counter and the run counter must both be zero.

One thing we take from NOVA and one thing we refuse. Take the cascade. Refuse the ranking step where a model picks the most promising of four candidates before any run — at forty seconds a run, that spends tokens we are scored on to save time we are not.

**Substeps**

**7.1 — Create harness/verify.py and make the rules file the single source**

Move contract.py’s hardcoded fragments and patterns into rules.jsonl as static rules. After this, adding a constraint is a line in a data file and never a code change — which is also what makes the constraint layer legible to a judge reading the repository.

```
def omega(diff, rules) -> list[Trip]:          # level 1 · regex · ~0 s
    for r in [r for r in rules if r.check == "static"]:
        hit = re.search(r.pattern, diff)
        if (r.mode == "forbid") == bool(hit):
            yield Trip(r.id, r.statement, r.severity)
```

**7.2 — Add the semantic level as one call returning booleans**

Send the diff and the statements of the llm-checked rules; expect one boolean per statement plus the line it relies on. Parse strictly and reject any numeric field in the response — the model is judging code, and a model that starts estimating scores here has crossed the line step 8 makes structural.

**7.3 — Compose the cascade with a real short circuit**

```
def cascade(diff, rules, llm, runner, node) -> Decision:
    for level, check in (("omega", omega), ("v_sem", v_sem)):
        trips = check(diff, rules, ...)
        if any(t.severity == "fail" for t in trips):
            return Decision.reject(level, trips)   # no LLM call, no run
    res = runner.run(node, "smoke", timeout_s=SMOKE_TIMEOUT_S)
    return Decision.accept() if res.ok else Decision.reject("smoke", res.failure_class)
```

**7.4 — Emit one event per level, carrying the rule id**

So a rejection is reconstructible from the log alone: which level, which rule, which round. This is also the data step 9 turns into forbidden patterns.

> **EXECUTE**

**NEW** harness/verify.py the four-level cascade, ~90 lines
**EDIT** harness/agents/contract.py move its hardcoded lists into rules.jsonl, then delete them
**EDIT** candidate/rules.jsonl absorb contract.py's patterns as static rules
**NEW** tests/test_14_verify.py

```
# harness/verify.py
import json, re
from dataclasses import dataclass
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parents[1] / "candidate" / "rules.jsonl"

@dataclass(frozen=True)
class Trip:
    rule_id: str; statement: str; severity: str

def load_rules(path=RULES_PATH):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def omega(diff: str, rules) -> list[Trip]:            # level 1 · ~0 s
    trips = []
    for r in rules:
        if r["check"] != "static":
            continue
        hit = bool(re.search(r["pattern"], diff))
        if (r["mode"] == "forbid") == hit:            # forbid+hit, require+miss
            trips.append(Trip(r["id"], r["statement"], r["severity"]))
    return trips

def v_sem(diff: str, rules, llm) -> list[Trip]:       # level 2 · one call · ~3 s
    stmts = [r for r in rules if r["check"] == "llm"]
    answers = llm.judge(diff, [r["statement"] for r in stmts])   # booleans only
    if any(isinstance(v, float) for v in answers.values()):
        raise ValueError("semantic judge returned a number")     # capability 6
    return [Trip(r["id"], r["statement"], r["severity"])
            for r, ok in zip(stmts, answers.values()) if not ok]

def cascade(diff, rules, llm, runner, node) -> tuple[bool, str, list[Trip]]:
    for level, fn in (("omega", lambda: omega(diff, rules)),
                      ("v_sem", lambda: v_sem(diff, rules, llm))):
        trips = fn()
        if any(t.severity == "fail" for t in trips):
            return False, level, trips                # NO llm call, NO run
    res = runner.run(node, "smoke", timeout_s=60.0)    # level 3
    return (True, "accept", []) if res.ok else (False, "smoke", [])
```

**Verify:** the economic claim directly, with counters rather than outcomes: construct a diff that trips a static rule, run cascade, and assert llm.calls == 0 and runner.runs == 0. Then add a throwaway rule to rules.jsonl, watch behaviour change with no code edit, and delete it. If everything is rejected, it is C3 from step 6 — print the trip list, never a boolean.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_omega_forbid_trips | A diff reading validation click labels trips C1. | Uses a realistic diff, not the regex’s own source string. |
| test_omega_require_trips | A diff without report.progress trips C5. | The require-mode twin; forbid and require fail in opposite directions and both need cover. |
| test_clean_diff_passes_all_levels | The shipped template passes every level. | Affirmative twin. A cascade that rejects everything satisfies both tests above. |
| ⚠ fails today · test_cascade_short_circuits | When level one trips, llm.calls == 0 and runner.runs == 0. | Asserts on counters, so a cascade that runs everything and discards the results still fails. This is the economic claim, tested directly. |
| test_v_sem_rejects_numeric_fields | A semantic response containing a float raises. | Refusal twin for step 8’s principle, enforced at the point the model speaks. |
| test_rules_file_is_the_only_source | contract.py contains no literal pattern list. | A grep assertion; catches a half-finished migration that leaves two sources of truth. |

**GATE:**
Adding a rule to rules.jsonl changes behaviour with no code change — demonstrate it once with a throwaway rule and delete it.

**If you drift here**

Symptom: everything is rejected. Almost certainly C3 from step 6. Print the trip list rather than the boolean — the cascade should always tell you which rule and which level, and if it cannot, fix that before debugging anything else.

Symptom: the semantic level is slow or flaky. Make it fail open with a logged warning, never fail closed. A flaky judge that blocks valid candidates costs rounds; one that lets a bad candidate through costs forty seconds, and the smoke level is right behind it.

---

### STEP 8 — Make numerical honesty structural
`~30 min | needs step 1 | cheapest step here`

**Current state**

- `[TREE]` Observed as a convention and enforced nowhere. EventLog.emit accepts arbitrary keyword fields from any caller.
- `[TREE]` One model-produced number is legitimate and load-bearing: Hypothesis.expected_gain, which drives queue order through Queue.score_hyp.

Why the rule is about provenance, not about floats

AgentX’s principle is that a model may be wrong about judgment and never about an objective fact. The naive reading — models may not produce numbers — is wrong here, because a forecast is a judgment and forecasts are how the queue is ordered. The workable rule is that a model may forecast and only the measurement layer may report. Twenty lines at the single choke point, and it converts a principle into something a judge can check in one command.

It also settles arguments elsewhere without further debate. Any design in which a model ranks untested candidates now fails at the type boundary rather than on discussion — which is why this step comes before the loop capabilities rather than after them. They are born compliant.

**Substeps**

**8.1 — Guard emit**

```
MEASURED = {"delta_mean", "delta_per_seed", "band", "score",
            "gauc", "ndcg_at_5", "primary", "holdout_score", "oracle_score"}

def emit(self, type, **fields):
    if MEASURED & fields.keys() and fields.get("producer") != "measure":
        raise NumericProvenanceError(sorted(MEASURED & fields.keys()))
```

**8.2 — Give forecasts their own namespace and keep them out of verdicts**

expected_* fields may appear on hypothesis_queued and nowhere else. One namespace per kind of number, checked rather than remembered.

> **EXECUTE**

**EDIT** harness/events.py EventLog.emit, ~line 69
**EDIT** harness/measure.py pass producer="measure" wherever it emits
**NEW** tests/test_15_provenance.py

```
# harness/events.py
class NumericProvenanceError(Exception):
    pass

MEASURED = frozenset({"delta_mean", "delta_per_seed", "band", "score",
                      "gauc", "ndcg_at_5", "primary",
                      "holdout_score", "oracle_score", "oracle_delta"})

def emit(self, type: str, **fields):
    leaked = MEASURED & fields.keys()
    if leaked and fields.get("producer") != "measure":
        raise NumericProvenanceError(sorted(leaked))
    if type != "hypothesis_queued":
        assert not any(k.startswith("expected_") for k in fields), \
            "a forecast may not enter a verdict"
    ...  # existing body
```

**Verify:** pytest -q tests/test_15_provenance.py passes both twins — an agent-sourced emit carrying delta_mean raises, and the measure path still works. Then fold a completed fake run and assert no numeric field lacks a producer. If the guard fires on a path you had forgotten, that is the step working: add producer="measure" only if the number genuinely came from task.score.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_agent_cannot_emit_a_metric | An agent-sourced emit carrying delta_mean raises. | Refusal twin, and the whole point. |
| test_measure_can_emit_a_metric | The permitted path still works. | Affirmative twin. A guard that blocks everything is not a guard. |
| test_expected_gain_never_enters_a_verdict | No verdict event carries an expected_* field. | Encodes the actual rule rather than its approximation. |
| test_every_number_in_a_run_has_a_producer | A fold over a completed fake run finds no orphan numeric field. | Whole-log assertion, so a new code path that emits numbers is caught the day it appears. |

**GATE:**
The last test passes over the golden run fixture, and the write-up can state numeric provenance as a checked property.

**If you drift here**

Symptom: the guard fires on a legitimate path you had forgotten about. Good — that is the step working. Add producer="measure" only if the number genuinely came from task.score. If it did not, you have found a real problem, and passing the flag to silence it is the one shortcut on this page that would invalidate the submission’s central claim.

---

### STEP 9 — Repair the memory and fix the feedback shape
`~80 min | needs step 8 | defect · thirty blank lines`

**Current state**

- `[TREE]` The pipe is connected at both ends. Tree._append_lesson (tree.py:432) writes to lessons.jsonl after every full-rung run; researcher.propose reads the last thirty and pastes them into the prompt.
- `[TREE]` The two ends disagree about the schema. The writer emits node, family, delta, gpu_min, diff_summary. The reader at researcher.py:165 formats f"- {l.get('heading','lesson')}: {l.get('text','')}" — two keys nobody writes. Every lesson arrives as - lesson: and nothing after it.
- `[TREE]` Nothing rejects a repeat. Lessons are advisory text in a prompt; a forbidden pattern is never enforced.
- `[TREE]` Queue.score_hyp (tree.py:192) ranks on (mean_delta + sd) / gpu_min with a cold-start fallback to expected_gain / expected_gpu_h. The shape is right — one key, no six weights — keep that. The denominator is not: gpu-min is identically zero on a CPU pipeline, and tree.py:198 clamps it to 1e-9, so every family with data scores (mean+sd)·109 and outranks every cold-start family by nine orders of magnitude.

The distinction the whole step turns on

An agent with no memory of failure re-proposes broken ideas, and each repeat costs a round out of a fixed budget. An agent that forbids every disappointment forbids its way into a corner. So the memory must distinguish a change that was defective — crashed, diverged, silently dropped a third of the data — from one that was merely unhelpful in one configuration. The first must never return. The second may well work later attached to a different parent.

That is why no_gain is deliberately excluded from the forbidden set, and why the exclusion is pinned by a test: it is exactly the line a later edit would quietly cross to make the loop “more efficient”, turning the memory into a ratchet.

**Substeps**

**9.1 — Agree one schema, with a closed vocabulary for the defect**

```
DEFECTS = {"crash", "diverged", "timeout",
           "silently_drops_rows", "leak_suspected", "no_gain"}

{"round": 7, "node": 12, "family": "objective/pairwise",
 "pattern": "pairwise loss without a valid-pair guard",
 "defect": "silently_drops_rows", "delta": -0.0031, "verdict": "rejected"}
```

An unrecognised defect raises rather than being stored, so the vocabulary cannot drift into free text over ten rounds.

**9.2 — Fold the forbidden set and filter before the model is called**

```
def forbidden(lessons) -> set[str]:
    return {l.pattern for l in lessons
            if l.verdict == "rejected" and l.defect != "no_gain"}

def admissible(hyp, forbidden) -> bool:   # before any token is spent
    return hyp.pattern not in forbidden
```

**9.3 — Fix the reader and delete the mismatch permanently**

Do not add heading and text to the writer to make the reader work. Change the reader to render the agreed schema, and add the round-trip test below so the two ends can never diverge silently again.

**9.4 — Give the round a fixed feedback shape**

Three fields and nothing else crosses the boundary: weak_components, directions capped at three and each carrying a citation or the literal no prior, and forbidden. Composed by a pure fold with no model involved, then rendered as three headings.

The reason for the cap and the citation requirement is the same: free-form history grows without bound, and a model reading raw history will confidently infer patterns from three noisy numbers. The shape is the defence.

> **EXECUTE**

**EDIT** harness/tree.py line 432 · _append_lesson writes the agreed schema
**EDIT** harness/agents/researcher.py line 165 · read the keys that are actually written
**NEW** harness/feedback.py the three-field fold
**NEW** tests/test_16_memory.py

```
# harness/tree.py:432 — one schema, both sides, closed defect vocabulary
DEFECTS = frozenset({"crash", "diverged", "timeout",
                     "silently_drops_rows", "leak_suspected", "no_gain"})

def _append_lesson(self, node, family, pattern, defect, delta, verdict):
    assert defect in DEFECTS, f"unknown defect: {defect}"
    row = {"round": self.round, "node": node.id, "family": family,
           "pattern": pattern, "defect": defect,
           "delta": delta, "verdict": verdict}
    with self._lessons_path.open("a") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")

# harness/agents/researcher.py:165 — fix the READER. do NOT add heading/text
# to the writer to make the old formatter work; that hides the bug again.
- f"- {l.get('heading','lesson')}: {l.get('text','')}"
+ f"- [{l['defect']}] {l['pattern']} (round {l['round']}, delta {l['delta']})"
```

```
# harness/feedback.py — pure folds, no model involved
def forbidden(lessons) -> set[str]:
    return {l["pattern"] for l in lessons
            if l["verdict"] == "rejected" and l["defect"] != "no_gain"}
    # no_gain is deliberately excluded: unhelpful once is not defective.
    # test_no_gain_is_not_forbidden pins this so no later edit can ratchet it.

def admissible(hyp, forb) -> bool:      # called BEFORE any token is spent
    return hyp.pattern not in forb

@dataclass(frozen=True)
class Feedback:
    weak_components: list[str]
    directions: list[str]               # ≤3, each with a citation or "no prior"
    forbidden: list[str]

def render(fb) -> str:                  # three headings, fixed order, no prose
    ...

# Queue.score_hyp (tree.py:192) — KEEP the shape (one key, no weights), CHANGE
# the denominator and the cold-start key. gpu_min is identically zero on CPU and
# tree.py:198 clamps it to 1e-9, which makes the ranking arithmetic meaningless.
- return (mean_delta + sd) / max(gpu_min, 1e-9)          # families with data
- return hyp.expected_gain / hyp.expected_gpu_h          # cold start
+ return (mean_delta + sd) / max(wall_s, 1.0)            # wall-clock seconds, from the events
+ return hyp.p_win                                        # P(clearing eps) — see step 13.1

# and the token counter (deliverable 4): every researcher call emits
# tokens_in / tokens_out on its hypothesis_queued event; the total is a fold.
events.emit("hypothesis_queued", ..., tokens_in=resp.usage.input, tokens_out=resp.usage.output)
```

**Verify:** the round trip end to end: write a lesson through Tree, render it through the researcher’s formatter, and assert the resulting line contains the pattern. Run this on the previous commit first and watch it produce - lesson: with nothing after it. Then re-propose a forbidden pattern and assert llm.calls == 0.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| ⚠ fails today · test_lesson_survives_the_round_trip | A lesson written through the tree, read through the researcher’s formatter, renders a line containing the pattern. | Fails today. It crosses the writer/reader boundary in one test, which is the only place the defect is visible — each side is individually correct. |
| test_defect_class_is_closed | An unknown defect string raises. | Refusal twin; keeps the vocabulary finite. |
| test_no_gain_is_not_forbidden | A no_gain rejection does not enter the forbidden set. | Pins the judgement, so the ratchet cannot be introduced by a later well-meaning edit. |
| test_forbidden_filter_precedes_the_llm | Proposing a forbidden pattern leaves llm.calls == 0. | Counter assertion, same discipline as the cascade. |
| test_forbidden_is_a_fold | Rebuilding from the log reproduces the live set exactly. | Determinism rule; the memory must survive a crash and resume. |
| test_render_has_exactly_three_headings | The rendered feedback has three headings, fixed order. | A fourth field means someone routed around the contract. |
| test_prompt_contains_no_raw_event_json | No event-log JSON appears in the researcher prompt. | Catches history leaking in by a second path, which is how fixed-shape briefs decay. |

**GATE:**
A deliberately re-proposed defective pattern is rejected with zero tokens spent, and the rejection names the round that first produced it.

**If you drift here**

Symptom: the forbidden set grows every round and proposals dry up. Check the defect classification — something is being filed as defective when it was only unhelpful. The fold is one function; print it each round while you are stabilising.

---

### STEP 10 — Replace the attribution constant with a function
`~60 min | needs step 9 | defect · gate permanently open`

**Current state**

- `[TREE]` The gate is fully built and permanently open. measure.verdict takes an attribution argument; at measure.py:398 a value of "unclear" blocks promotion with the reason replicate pass but attribution unclear. There is a passing test at test_05_measure_pure.py:252.
- `[TREE]` tree.py:51 reads ATTRIBUTION_HAND = "clear", and that constant is what is passed at both call sites — tree.py:638 and tree.py:695. Every verdict ever produced declared its attribution clear before looking at anything.

> **THE HIGHEST-LEVERAGE EDIT IN THIS DOCUMENT**

We are not building attribution. The socket, the gate, the event field and the test all exist. We are replacing one constant with one function — which is why a step that sounds like the most sophisticated capability on the list takes an hour.

What attribution actually asks

The score went up. Did the thing you changed cause it? These are different questions and only the second one compounds. If a gain came from somewhere other than the stated mechanism, the lesson written into memory is false, and the next three rounds chase a mechanism that never worked. AgentX’s answer is to make the claim falsifiable before the code is written: name the mechanism, name the observables that must move if it is real, then check them.

An unclear verdict is not a rejection. The number stands; what is withheld is promotion and the lesson. And note what it does not do — it does not stop the organizers’ convergence counter, which is defined on validation score and is not ours. What it prevents is a node becoming the incumbent on a story we cannot support, which matters because every later delta is measured against the incumbent.

**Substeps**

**10.1 — Make proposals declare observables, and refuse ones that do not**

Edit surface, mechanism, observables. A proposal missing any of the three is not a proposal. This is the one thing kept from AgentX’s six-term score, kept as a gate rather than a weight.

**10.2 — Give Hypothesis the fields steps 9 and 10 assume**

It currently carries id, stage, mechanism, description, citation, expected_gain, expected_gpu_h, parent_node and patch — no pattern, no claim. Add both to types.py, and add them to researcher.HYPOTHESIS_SCHEMA as well, or the schema validator rejects the model output that carries them.

**10.3 — Require at least one harness-computed observable per claim**

The hole this closes is worth understanding rather than just patching. Two of the three pairwise observables — train_logloss and valid_pairs_per_epoch — can only come from inside the candidate, riding on the metrics dict of report.result. So a generated candidate would be supplying the evidence used to judge whether that candidate’s story is true. One that reported a plausible pair count would pass attribution while doing nothing of the kind.

The rule: every claim must include at least one observable computed harness-side from task.score — here, the comparison of GAUC movement against nDCG movement. Candidate-reported observables may corroborate; they may never be the only evidence. One assertion in the proposal gate, and it is the difference between attribution and self-certification.

```
assert any(o.source == "harness" for o in claim.observables), \
    "a claim needs at least one observable the candidate cannot write"
```

**10.4 — Write attribute() and fail safe toward unclear**

```
def attribute(claim, before, after) -> Literal["clear", "unclear"]:
    for o in claim.observables:
        if o.name not in after:
            return "unclear"        # missing evidence is never clear
        if not moved_as_declared(o, before[o.name], after[o.name]):
            return "unclear"
    return "clear"
```

The direction of the fail-safe is the entire design. Absent evidence must resolve to unclear, or a missing observable silently becomes a pass.

**10.5 — Delete ATTRIBUTION_HAND and pass the computed value**

Both call sites. Delete the constant rather than defaulting it — a default is a jumper wire someone will re-solder under time pressure.

**10.6 — Define the observables for the first hypothesis you will actually run**

The pairwise-loss swap is the likely first proposal, and its three observables are all one line away:

| Observable | Must move | Why this one |
|---|---|---|
| gauc_delta > ndcg_delta | true | A pairwise objective is a within-user ordering change. If both halves move together, whatever helped was not ordering. |
| train_logloss | worse | The counter-intuitive one and the most diagnostic. Optimising ranking should degrade calibration; if both improve, the change did something else. |
| valid_pairs_per_epoch | > 0, logged | 36.3% of test users can form no valid pair — 27.1% have no positive, 9.2% are all-positive (measure valid’s own figures in step 2.2). Without this count, “pairwise worked” and “dropping a third of the users worked” are the same number. |

> **EXECUTE**

**NEW** harness/attribute.py Claim, Observable, attribute()
**DEL** harness/tree.py:51 ATTRIBUTION_HAND — remove it, do not default it
**EDIT** harness/tree.py lines 638 and 695 · pass the computed value
**EDIT** hypotheses/bank.yaml every entry declares observables
**NEW** tests/test_17_attribution.py

```
# harness/attribute.py
@dataclass(frozen=True)
class Observable:
    name: str
    direction: str          # "up" | "down" | "positive" | "greater_than:<other>"

@dataclass(frozen=True)
class Claim:
    mechanism: str
    observables: list[Observable]

def attribute(claim, before: dict, after: dict) -> str:
    for o in claim.observables:
        if o.name not in after or o.name not in before:
            return "unclear"          # missing evidence is NEVER clear
        if not _moved(o, before[o.name], after[o.name]):
            return "unclear"
    return "clear"
```

```
# harness/tree.py — delete the constant, compute at both call sites
- ATTRIBUTION_HAND = "clear"
- attribution=self.attribution,
+ attribution=attribute(hyp.claim, inc_observables, node_observables),

# hypotheses/bank.yaml — the first hypothesis you will actually run
- id: obj-pairwise
  stage: objective
  mechanism: pairwise
  citation: "organisers' ranked direction 2"
  observables:
    - {name: gauc_minus_ndcg_delta, direction: positive}   # ordering, not calibration
    - {name: train_logloss,         direction: up}         # ranking degrades calibration
    - {name: valid_pairs_per_epoch, direction: positive}   # 36.3% form no pair
```

**Verify:** grep -rn ATTRIBUTION_HAND harness/ returns nothing, and a real run produces at least one unclear verdict whose reason a reader can check. If everything comes back unclear, the observables are probably not captured for the incumbent — attribution is a comparison, and a missing before reads as missing evidence. Print both dictionaries for one node before touching anything else.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| ⚠ fails today · test_attribution_is_computed_not_constant | No module-level attribution constant reaches a verdict. | Fails today. A grep-and-call-graph assertion; a re-introduced default is caught immediately. |
| test_all_observables_moved_is_clear | Full movement yields clear. | Affirmative twin, so the gate cannot be soldered shut the other way. |
| test_partial_movement_is_unclear | Two of three moving is not attribution. | The realistic case, and the one a lenient implementation would pass. |
| test_missing_observable_is_unclear | Absent evidence yields unclear. | Pins the fail-safe direction, which is the whole design. |
| test_unclear_blocks_promotion | Already passing at test_05_measure_pure.py:252. | Listed as proof that only the computation was ever missing. |
| test_valid_pair_count_is_emitted | The observable exists in the log before the pairwise hypothesis runs. | Ensures the evidence is available at the moment it is needed, not added afterwards. |

**GATE:**
grep -rn ATTRIBUTION_HAND harness/ returns nothing, and at least one node in a real run carries an unclear verdict for a reason a reader can check.

**If you drift here**

Symptom: every node comes back unclear and nothing promotes. Check whether the observables are being captured for the incumbent as well as the candidate — attribution is a comparison, and a missing before reads as missing evidence. Print both dictionaries side by side for one node before touching the thresholds.

Symptom: you are tempted to default the argument to "clear" so the run proceeds. That is precisely the defect this step removes, and it will look like working code to whoever reads it next.

---

### STEP 11 — Make the search policy explicit
`~45 min | needs step 10`

**Current state**

- `[TREE]` The structure is fully present. tree.py has the tree, the node states, the legal-transition check, and the constants that encode the policy: MAX_LIVE_BRANCHES = 3, DEBUG_DEPTH = 3, SCREEN_SEED = 1, FULL_SEEDS = (1,2,3). Node.kind admits draft, improve, debug, ablate, trial and ensemble.
- `[TREE]` What is missing is the function that reads the tree and returns the next move. That choice is currently spread across the run loop, so it cannot be tested in isolation or replayed from the log.

Why a policy function rather than a better loop

AIDE (arXiv:2502.13138) treats the run as a tree of whole solutions and picks a move type under a fixed policy: draft a new root, improve an existing node, or debug a broken one, with a hard limit on repeated debugging. Always extending the current best collapses into one lineage and gets stuck when that lineage has a flaw near its root; always drafting throws away everything learned.

The breadth floor comes from elsewhere. AIRA-2 finds the compute-optimal number of parallel attempts grows with the square root of the budget — breadth over depth. Three drafts before the first improve is that finding at our scale, and it is also what makes the round policy work: we screen every survivor rather than asking a model to pick one, because at forty seconds a run, measuring is cheaper than guessing.

**Substeps**

**11.1 — Extract one pure function**

```
DRAFTS_MIN = 3          # breadth floor

def select(nodes, budget_left_s) -> Move:
    live = [n for n in nodes if n.state in ("running", "replicating")]
    if len(live) >= MAX_LIVE_BRANCHES:
        return Move(None, None, "at branch cap")

    drafts = [n for n in nodes if n.kind == "draft" and n.state == "promoted"]
    if len(drafts) < DRAFTS_MIN:
        return Move("draft", None, "breadth floor")

    broken = [n for n in nodes
              if n.state == "failed" and debug_depth(n, nodes) < DEBUG_DEPTH]
    if broken:
        return Move("debug", best(broken), "repair before extend")

    return Move("improve", argmax(promoted(nodes)), "extend best")
```

**11.2 — Empty the run loop of its own branching**

It should call select() and act. Every conditional left behind is a decision that will not appear in the log and cannot be replayed.

**11.3 — Emit the move and its reason**

The reason string is what lets a reader — or you, at hour thirty — understand why the run spent four rounds debugging instead of exploring.

> **EXECUTE**

**EDIT** harness/tree.py add select(); empty the run loop of its own branching
**NEW** tests/test_18_topology.py

```
# harness/tree.py — one pure function. no side effects, no I/O.
DRAFTS_MIN = 3          # breadth floor; AIRA-2: parallelism ~ sqrt(budget)

@dataclass(frozen=True)
class Move:
    kind: str | None; parent: int | None; reason: str

def select(nodes, budget_left_s) -> Move:
    live = [n for n in nodes if n.state in ("running", "replicating")]
    if len(live) >= MAX_LIVE_BRANCHES:                     # = 3
        return Move(None, None, "at branch cap")

    drafts = [n for n in nodes if n.kind == "draft" and n.state == "promoted"]
    if len(drafts) < DRAFTS_MIN:
        return Move("draft", None, "breadth floor")

    broken = [n for n in nodes
              if n.state == "failed" and _debug_depth(n, nodes) < DEBUG_DEPTH]
    if broken:
        return Move("debug", _best(broken).id, "repair before extend")

    return Move("improve", _argmax_promoted(nodes).id, "extend best")

# the run loop calls select() REPEATEDLY until it returns the at-cap move.
# that is what gives three candidates in flight per round; the runs inside
# the round are sequential on one core (3 screens x 40 s = 2 min), which is
# what the ten-minute round budget already assumed. workers stays 1.
# every conditional left in the loop is a decision that will not appear in
# the log and cannot be replayed.
self.events.emit("move_selected", kind=m.kind, parent=m.parent, reason=m.reason)
```

**Verify:** replay the golden run’s event log and confirm the identical sequence of moves. Then check the loop is actually empty: grep -n 'if .*state ==\|if .*kind ==' harness/tree.py should show hits inside select and nowhere in the run loop. If more than half of a run’s rounds are repairs, the candidate template is the problem — go back to step 6, not to DEBUG_DEPTH.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_select_drafts_until_min | Two promoted drafts and no failures yields draft. | Constructed node lists, no run required, so the policy is tested rather than the loop. |
| test_select_repairs_before_extending | A failed node under the depth limit outranks an improve. | Pins the ordering, which is the only interesting thing about the policy. |
| test_debug_depth_is_capped | A node debugged three times is abandoned. | Refusal twin; the runaway-repair failure mode. |
| test_branch_cap_blocks_spawn | Three live branches yields a null move. | Counter assertion — no fourth process is started, not merely no fourth move returned. |
| test_select_is_a_fold | The same node list yields the same move, twice. | Determinism rule. Without it the run is not reproducible and the log is not evidence. |

**GATE:**
Replaying the golden run’s event log reproduces the identical sequence of moves.

**If you drift here**

Symptom: the run spends everything on debugging. DEBUG_DEPTH is doing its job per-node but nothing caps it globally. If more than half the rounds are repairs, the candidate template is the problem, not the policy — go back to step 6.

---

### STEP 12 — Build the monitors and derive the claim
`~70 min | needs step 4 | the differentiator`

**Current state**

- `[TREE]` Nothing exists. No overfitting monitor, and the autonomy level is not computed anywhere — it would be typed into the write-up by hand.
- `[TREE]` measure.py:31 holds LADDER_ETA, recalibrated in step 5. The count of accepted ladder steps is the number of adaptive queries against the split.

Why this is the differentiator and not a disclaimer

Every team has the labels on disk, so nobody is protected by secrecy and everyone is selecting on the same split. A team that tunes hard against it will report a higher number, and honesty will not close that gap. We cannot out-score that by being careful. What we can do is report a quantity none of them have: the distance between the signal that selected our model and a signal the selection could not influence, tracked at every promotion rather than computed once at the end.

The literature is unusually encouraging here and worth reading before you build. Blum and Hardt’s Ladder is the mechanism we already implemented without knowing it. Dwork’s adaptive-data-analysis bound is stated in the number of queries, which is why the visit count belongs in the report rather than being minimised. arXiv:1905.12580 finds leaderboard overfitting is milder in practice than theory predicts, because submitted models are similar to one another. And the ImageNet retest (arXiv:1902.10811) found absolute accuracy dropped substantially while model ranking was almost perfectly preserved — which is exactly our position, and the reason rank correlation is the number that matters most.

**Substeps**

**12.1 — Three folds in harness/overfit.py, no new runs**

```
def oracle_gap(events)      # per promotion: val delta minus oracle delta
def seed_consistency(node)  # fraction of 3 seeds sharing the mean's sign
def split_rank_corr(events) # Spearman: val ranking vs oracle ranking
                            # returns None below 3 promotions — never 0.0
def ladder_queries(events)  # accepted steps = adaptive query count
```

**12.2 — Give each monitor a trip condition and a named action**

| Monitor | Trips when | Action |
|---|---|---|
| Oracle gap every promotion | widens over 3 consecutive promotions | Raise the bar: require the oracle delta to be positive, not merely the validation delta. Costs nothing and the search cannot game it. |
| Seed consistency every replicate | < 3 of 3 seeds share the sign | Downgrade to inconclusive and re-queue at lower priority — measure.inconclusive_next already does this. |
| Rank correlation once, at the end | ρ < 0.6 (n ≥ 3) | Report either way. High is the strongest defence available; low is a finding to state plainly rather than hide. |

**12.3 — Derive the autonomy claim from the log**

```
def claim_level(events) -> str:
    promos = [e for e in events if e.type == "verdict" and e.state == "promoted"]
    if not promos:                                     return "L3"
    if not all(has_oracle_reading(e, events) for e in promos): return "L4-m"
    return "L4-v"
```

The value is that it can go down. If the oracle wiring is unfinished the report says L4-m in our own words, before a judge has to work it out. A system that states a weaker claim when the evidence is weaker is making a stronger claim overall — that its claims track its evidence at all.

> **EXECUTE**

**NEW** harness/overfit.py three folds plus the query count
**EDIT** harness/outputs.py claim_level(); report() prints the four numbers
**NEW** tests/test_19_monitors.py

```
# harness/overfit.py — folds over the event log. no new runs, no run state.
def _promotions(events):
    return [e for e in events
            if e.get("type") == "verdict" and e.get("state") == "promoted"]

def oracle_gap(events) -> list[tuple[int, float]]:
    return [(e["node"], e["delta_mean"] - e["oracle_delta"]) for e in _promotions(events)]

def gap_alarm(events) -> bool:
    gaps = [g for _, g in oracle_gap(events)]
    if len(gaps) < 3:
        return False                       # 3 promotions minimum. never react to one.
    return gaps[-1] > gaps[-2] > gaps[-3]

def seed_consistency(delta_per_seed) -> float:
    m = statistics.mean(delta_per_seed)
    return sum(1 for d in delta_per_seed if (d > 0) == (m > 0)) / len(delta_per_seed)

def split_rank_corr(events) -> float | None:
    p = _promotions(events)
    if len(p) < 3:
        return None                        # UNDEFINED, not 0.0 — a zero would
    ...                                    # render as a catastrophic finding

def ladder_queries(events) -> int:
    return len(_promotions(events))        # = adaptive queries, for the report
```

```
# harness/outputs.py — the claim is a return value, never a string in a template
def claim_level(events) -> str:
    promos = _promotions(events)
    if not promos:                                                   return "L3"
    if not all("oracle_delta" in e for e in promos):                 return "L4-m"
    return "L4-v"
```

**Verify:** the one test that proves the claim is derived rather than typed: copy a completed log, strip every oracle_delta, regenerate the report, and confirm the rung changed to L4-m. If it did not change, the level is hardcoded somewhere — grep -rn 'L4-v' harness/ app/ and remove every literal but the one inside claim_level.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_oracle_gap_is_a_fold | Computed from the log alone, no run state. | Must survive a crash and resume, which a stateful monitor would not. |
| test_gap_alarm_needs_three_promotions | A single divergent promotion does not trip it. | Guards against reacting to the very noise being measured. |
| test_rank_corr_returns_none_below_three | Undefined is None, not 0.0. | A zero would render in the report as a catastrophic finding when it means no data. This is a real reporting bug, caught by a two-line test. |
| test_seed_sign_flip_downgrades | Two of three seeds yields inconclusive. | Refusal twin against a monitor that only logs. |
| test_ladder_queries_matches_promotions | The reported query count is derived. | The number goes in the write-up; it must not be typed. |
| ⚠ fails today · test_claim_downgrades_without_oracle | Promotions with no oracle readings yield L4-m. | Deleting oracle events from a copy of the log must change the regenerated report. Nothing else proves the claim is derived. |

**GATE:**
The report carries four numbers nobody has to trust us about: the primary score, its spread over seeds, the oracle gap trend, and the number of adaptive queries that produced it.

**If you drift here**

Symptom: the oracle gap looks alarming after two promotions. Two is not three, and the alarm exists because a single divergent reading is expected. Wait for the third rather than adding a correction that will itself need explaining.

---

### STEP 13 — Seed the bank and run it
`~45 min setup · hours unattended | needs 1–12`

**Current state**

- `[TREE]` hypotheses/bank.yaml holds ten entries. Eight aim at published dead ends and two name Ali-CCP columns that do not exist in this dataset. As it stands the bank would spend the entire budget re-testing known negatives.
- `[TREE]` Each entry carries expected_gain and expected_gpu_h, which are what Queue.score_hyp used before any family had data. After step 9 the cold-start key is p_win and there is no GPU-hour field: under N = 3 the counter resets on any single win, so a reliable +0.004 outranks a 30%-chance +0.02, and expected_gain encodes the wrong ordering.

Where proposals come from, and why there is no research agent

NOVA runs a paper-reading agent because its space of changes is unbounded. Ours was enumerated by the organizers — a set of ranked directions and several measured dead ends. So we keep the function of research grounding, which is that every proposal cites a source, and drop the agent, because the grounding is already computed. Say this explicitly in the write-up, or it reads as though we skipped the expensive part rather than pre-paying it.

**Substeps**

**13.1 — Replace the bank with entries drawn from the organizers’ ranked directions**

Each with a citation, an honest p_win — the probability of clearing ε at all — and a declared observable set from step 10; loss-function variants first. Delete the eight dead ends rather than deprioritising them — a dead end left in the bank will be proposed eventually. Then seed the memory with them: write the organisers’ three published dead ends into rules.jsonl as round-0 forbidden patterns — static features are flat (13 fields 0.5940 vs 0.5950 for 5), capacity is flat (k = 8/16/32 → 0.5895 / 0.5902 / 0.5887), anything constant within a user contributes exactly zero. NOVA earns its forbidden list over thousands of rounds; ours was published before iteration zero, and step 9’s admissible() filter enforces it before a token is spent.

**13.2 — Do one supervised round end to end before leaving it alone**

Watch a single round complete: propose, gate, smoke, screen, replicate, oracle, attribute, learn. Confirm it lands under ten minutes and that every stage wrote an event. This is the only opportunity to catch a wiring error while it is still cheap.

Before that round, add the negative sentinel: a round in which every candidate is rejected at the gate or the smoke rung must record a negative delta for the round and continue to the next proposal, not fall through the loop. Under the convergence rule this is precisely the round the cascade is supposed to produce, and without the sentinel the loop wedges on the round where the contract gate is doing its job.

**13.3 — Then let it run, and do not intervene**

Intervening mid-run makes the log a record of two experiments. If something is wrong, stop, fix, and restart with a new run id — a clean short run is worth more than a long contaminated one, and the honesty of the log is the deliverable. Expect to intervene on the first run; log each one as a typed intervention event carrying the reason and the run id it ended. The count is scored directly under Autonomy, and an honest number with events behind it reads better than a suspiciously round zero.

> **EXECUTE**

**EDIT** hypotheses/bank.yaml delete the 8 dead ends and 2 Ali-CCP entries; write the real ones, keyed by p_win, no expected_gpu_h
**EDIT** candidate/rules.jsonl seed the three published dead ends as round-0 forbidden patterns
**EDIT** harness/tree.py negative sentinel: an all-rejected round records a negative delta and continues
**NEW** tests/fixtures/golden_run.jsonl the whole-log fixture
**NEW** tests/test_20_golden_run.py

```
# 1 — the fixture that catches everything the unit tests miss (doctrine rule 8)
python -m harness fake --instant --run-id golden
cp runs/golden/events.jsonl tests/fixtures/golden_run.jsonl
#   from here, any change that alters loop behaviour fails test_20 until you
#   update the fixture deliberately — which makes it visible in review.

# 2 — ONE supervised round, watched end to end. the only cheap chance to
#     catch a wiring error.
python -m harness run protocols/kuairand.yaml --max-nodes 3 --epochs 12
#     confirm every stage wrote an event and the round finished under ten minutes:
python - <<'PY'
import json, collections
ev = [json.loads(l) for l in open("runs/<run_id>/events.jsonl")]
print(collections.Counter(e["type"] for e in ev))
PY
#     expect: hypothesis_queued, verdict, state_changed, and one oracle visit

# 3 — then the real run. do not intervene.
python -m harness run protocols/kuairand.yaml --max-nodes 20 --epochs 12
#     20 ≤ the statement's 50-iteration cap; its 6 h clock is the run's, and the
#     organisers' ε/N rule will normally stop it well before either.
```

**Verify:** one full round completes in under ten minutes, every stage of the loop appears in the event counter, and pytest -q tests/test_20_golden_run.py is green. If you spot a bug mid-run, judge it by whether it changes what the numbers mean: a logging bug, carry on and note it; anything touching scoring, promotion or attribution, stop and restart with a new run id. A contaminated log cannot be cleaned afterwards.

**Tests**

| Test | Asserts | Cannot be faked because |
|---|---|---|
| test_bank_entries_have_citations | Every entry carries a citation or the literal no prior. | Blank is not allowed; an unsourced direction is indistinguishable from a hallucinated one. |
| test_bank_names_only_real_columns | Every column named exists in the dataset schema. | Checked against the file, catching the two Ali-CCP leftovers automatically. |
| test_no_dead_end_directions | No entry matches the organizers’ published negative list. | A data-driven check, so it keeps working as the bank grows. |
| test_dead_ends_are_seeded_forbidden | The three published dead ends are in forbidden(lessons) at round 0, and proposing one leaves llm.calls == 0. | The memory is checked, not the file: a seed that is written but not read would pass a file test. |
| test_bank_sorts_on_p_win | Entries carry p_win and no expected_gpu_h; the first three by p_win are loss-function variants. | Pins the ordering step 13.1 argues for, so a later edit cannot quietly restore expected_gain. |
| test_all_rejected_round_continues | A round whose every candidate is rejected before training emits a negative round delta and the next round starts. | The negative sentinel; without it this is the round on which the loop wedges, and no unit test above exercises it. |
| test_intervention_is_a_typed_event | Stopping a run through the CLI writes an intervention event with a reason. | The Autonomy score is a fold over these; an untyped log line cannot be counted. |
| test_golden_run_matches_fixture | An end-to-end fake run’s event log equals a checked-in fixture. | Rule 8. Catches every behaviour change the unit tests miss; updating the fixture is a deliberate, reviewable act. |

**GATE:**
One complete round under ten minutes, every stage present in the log, and the golden-run fixture green.

**If you drift here**

Symptom: the run is going and you notice a bug. Judge it by whether the bug changes what the numbers mean. A cosmetic logging bug — carry on and note it. Anything touching scoring, promotion or attribution — stop and restart. A contaminated log cannot be un-contaminated afterwards.

---

### STEP 14 — Write what the log will support
`~90 min | needs step 13`

The discipline

You are not writing a report generator — outputs.report(events, out_path) arrived with #16 in step 1, alongside write_submission and its read-back. Step 14 is calling them and writing prose around what they produce.

Write the results section by reading the log, not by remembering the plan. Every number in the write-up should be reproducible with one command against runs/<run_id>/events.jsonl. If a claim cannot be produced that way, it is not a result — it is an intention, and it belongs in the future-work paragraph where it costs nothing and misleads nobody.

**What goes in, in order**

- The claim, derived. The rung from claim_level(), with the sentence explaining what would have made it lower.
- The score, with spread, against the ceiling. Primary, its components, and the standard deviation across seeds — never a bare number — reported as a fraction of the oracle ceiling (0.8484 valid, 0.8645 test, from baseline_scores.json) rather than of 1.0, because 27.1% of test users are all-negative and no model can move their nDCG.
- The pass-rate factorisation. EPR = LPR × (1 − SFR): landing pass rate is the fraction of proposals that ran to completion, semantic failure rate the fraction of those that tripped a rule or an observable, effective pass rate their product. The log already separates the two failure kinds — a failure event is a landing failure, a rule trip a semantic one — so all three are folds.
- The oracle gap. The trend across promotions, and the rank correlation with its n. This is the part almost nobody else will have.
- The adaptive query count. Stated as a number, framed as the budget from Dwork’s bound rather than apologised for.
- The unclear verdicts. How many candidates measured well and were not promoted, and why. Withheld promotions are evidence the gate is real; a run with none looks like a gate that never closed.
- The organisers’ deliverables, exported. runs/<run_id>/iterations.jsonl — one row per iteration folded from the log: hypothesis, patch path, valid primary and its components, oracle delta, verdict, failure and recovery events, tokens in and out, wall-clock seconds; plus the totals (iterations used of 50, hours used of 6, tokens, interventions). This is the per-iteration run log the statement asks for and the source of the Cost and Autonomy numbers; one fold in outputs.py, cited beside the write-up.
- What we did not build, and why. The refusals — ranking before running, the four knowledge bases, the expert panel, self-improvement — each with its one-line reason. A defended refusal reads as judgement; an unmentioned one reads as an oversight.

> **DO NOT CLAIM**

That we did not overfit validation. Nobody can claim that. Claim instead that we measured it, which is the thing the survey says almost nobody does — and which the oracle gap in your own log demonstrates.

**GATE:**
Every number in the submission traces to one command against the event log, someone who has never seen the repository can run those commands, and python3 submit.py --check --split test submission.csv is green on the final CSV — the harness wrote it unattended, and the kit’s checker, not ours, accepts it.

—

### Deferred: ablation for weak components

[~50 min] [drop this one first]

MLE-STAR (arXiv:2506.15692) neutralises one block of the candidate’s code at a time and re-scores, reading off which block was actually carrying the result. It fills a gap NOVA declared itself: NOVA’s feedback format has a weak_components field and no method for computing it, so in practice a model guesses.

Node.kind already admits "ablate" and that string appears nowhere else in the harness — the seat was designed in and never sat in. Four blocks at screen rung, once after the first promotion, under three minutes total. It must never touch the oracle; four extra visits would spend the adaptivity budget on a diagnostic.

Why this is the right thing to drop: it is the only item on the list whose absence costs search quality rather than correctness. Everything else, omitted, makes a number less trustworthy. This one just makes the search slightly less well aimed, and the fallback — the stage with the worst mean delta — is a reasonable approximation.

## The papers, and what each one is for  ·  _reference_

One capability area, one owning paper. A second paper targeting an occupied area is rejected by default and admitted only if it beats the incumbent on a named axis that matters at our scale — not on general merit, and not because it is newer. If you are about to adopt a technique that is not in this table, that is the test it has to pass first.

| Field | Owner | What we take | Step |
|---|---|---|---|
| Search topology | AIDE | Tree over whole solutions; draft / improve / debug under a fixed policy with a depth limit. | 11 |
| Pre-run verification | NOVA | The cost-ordered cascade: constraints, semantic review, smoke, then measure. | 7 |
| Failure memory | NOVA | Forbidden patterns as records — pattern, defect class, round — generated by the run itself. | 9 |
| Feedback format | NOVA | Three fields as headings: weak components, directions, forbidden. | 9 |
| Attribution | AgentX | Declared policy plus observables; refuse to credit a gain whose observables did not move. | 10 |
| Numerical honesty | AgentX | A model may forecast; only measurement may report. | 8 |
| Evaluation integrity | AIRA-2 | Fixed splits, external scoring, steering decoupled from selection, breadth over depth. | 4 · 11 |
| Where to search next | MLE-STAR | Ablate the candidate’s own blocks. Fills NOVA’s declared gap — the only clean reason to admit a second paper. | deferred |
| Adaptive reuse of a split | Dwork et al. | Query count as the budget. The number to report, not to minimise. | 4 · 12 |
| Threshold ladder | Blum & Hardt | Report an improvement only above a threshold. We had already built it; now we can cite it. | 5 · 12 |
| How alarmed to be | Model similarity · ImageNet retest | Overfitting is milder in practice than theory says, and ranking survives even when absolute scores do not. | 12 |
| Autonomy claim | the survey | The L0–L5 ladder, and its failure list as a checklist of things not to claim. | 12 |
| Self-improvement | GEPA | Nothing this iteration. Named as the September route; it needs rollouts we will not have. | — |
| Two-loop validation | Self-Evolving RecSys | Framing only. Screen/replicate and oracle already are the two loops; a second mechanism would clash. | — |

## If the clock beats you

Drop in this order, and say in the write-up which ones you dropped. A stated omission is a decision; a silent one is a hole a judge will find.

- Ablation — costs search quality, not correctness.
- The explicit search policy — the existing loop still works, it is just not replayable. Note that the policy is implicit.
- The semantic level of the cascade — keep the constraint level and smoke. Two of three levels is still a cascade.
- The feedback shape — keep the memory repair, which is the part that is actually broken.

Never drop: the oracle path, the attribution function, the derived claim. Those three are the submission. Everything else is how well it was built.

Companion to The Pivot Sequence, which carries the architectural reasoning, the full paper cards with rejection arguments, and the ten capability scopes this runbook sequences. Facts marked tree were verified against beating-nise at 3e22b28 on 29 August 2026; facts marked given are inherited from the task-space and research-space pages and should be re-verified before a decision rests on one. Eight tests in this document are written to fail on the current tree, marked in red — run them and watch them fail before you make them pass. A test that was green before the work started tested nothing about the work.
