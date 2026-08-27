# Build steps

Source of truth for phased implementation. Each phase lists owners, interfaces, tests, and locked decisions.

---

## Phase 1 · Protocol and event log

**Owner** A: `protocol.py` · B: `events.py`  
**Depends on** phase 0  
**Source** Backend_plan §1, §4

### Goal

Load a protocol yaml, hash its ruler block canonically, and write a `run_started` event through a single-writer log that three threads can hammer without a torn line. After this phase you can `tail -f` a real log.

### In scope

`harness/protocol.py`, `harness/events.py`, `harness/__main__.py` (the `init` command only), `tests/test_01_protocol.py`, `tests/test_01_events.py`.

### Out of scope

Filling in any null in `aliccp.yaml`. Any event type other than `run_started` being emitted by real code (tests may emit any type). The web server. Reading the log back.

### Interfaces

```python
# harness/protocol.py
@dataclass
class Protocol:
    task: str
    schema_version: int
    ruler: dict
    run: dict
    protocol_hash: str
    path: Path

def load(path) -> Protocol
    # validates required keys; nulls allowed under ruler

def canonical_bytes(ruler: dict) -> bytes
    # sort keys recursively; floats via repr of float(x) so 0.10 == 0.1;
    # ints stay ints; None -> "null"; no whitespace; utf-8.
    # Comments never reach here (yaml drops them).

def protocol_hash(ruler: dict) -> str
    # "sha256:" + hex of canonical_bytes; run block NOT included


# harness/events.py
class EventLog:
    def __init__(self, run_dir: Path, run_id: str, protocol: Protocol): ...
        # opens events.jsonl and heartbeat.jsonl for append; starts one writer thread
        # first line written is run_started with the whole protocol dict embedded

    def emit(self, type: str, **fields) -> int
        # validates type in EVENT_TYPES and fields.get("state") in STATES if present;
        # requires "summary" (str); stamps schema_version=1, seq, t (ISO-8601 UTC),
        # run, protocol_hash; puts on queue; returns the seq it WILL get
        # (allocated under a lock, so monotonic)

    def new_node(self, parent: int | None) -> int
        # one counter, lock-protected

    def heartbeat(self, worker: str, **fields) -> None
        # goes to heartbeat.jsonl through the same queue

    def close(self) -> None
        # drains, fsyncs, joins thread; emit after close raises

    # writer thread: json.dumps(line) + "\n"; flush() every line;
    # os.fsync only when type in {"verdict","submission_written","run_ended"}


# python -m harness init protocols/synthetic.yaml
#   -> creates runs/<task>-<YYYYMMDD-HHMMSS>/ , writes run_started, closes,
#      prints the run id and hash
```

### Locked decisions (phase 1)

1. **Required keys** — top-level only: `schema_version`, `task`, `ruler`, `run`. Also check `ruler` is a non-empty dict. No nested schema this phase; `ValueError` names the missing key.
2. **`run_started` payload** — raw YAML body `{schema_version, task, ruler, run}` plus `protocol_hash` and `protocol_path` (as a string). Never the dataclass — the browser reads this line and must not see Python types.
3. **`init` output** — two lines: `run_id=<task>-<YYYYMMDD-HHMMSS>` then `protocol_hash=sha256:…`. UTC for the run id and for every `t` stamp.
4. **Heartbeat seq** — separate counter. Heartbeats get their own monotonic `seq` starting at 1 in `heartbeat.jsonl`, plus the same stamps (`schema_version`, `t`, `run`, `protocol_hash`, `type="heartbeat"`, `worker`). No summary required. Reason: the heartbeat endpoint's `?since=` needs its own sequence, and `events.jsonl` line counts must not move.
5. **`test_stubs_raise`** — data-driven: an `IMPLEMENTED = {"harness.protocol", "harness.events"}` set at the top of the test that each phase extends in its own PR; stubs outside the set must still raise.
6. **Ship** — commit when green on branch `phase-1-protocol-events`, open a PR against `main`, do not merge.

**Extras, locked:** `json.dumps(obj, separators=(",", ":"), sort_keys=False, ensure_ascii=False, default=str)`; stamp order `schema_version`, `seq`, `t`, `run`, `protocol_hash`, `type` before the caller's fields; flush every line; fsync on `verdict`, `submission_written`, `run_ended` only.

### Tests to pass — `tests/test_01_protocol.py`

- `test_reorder_same_hash` — the same ruler with top-level keys reordered hashes identically.
- `test_float_formatting_same_hash` — `0.10` and `0.1` and `1e-1` give the same hash.
- `test_comment_same_hash` — a yaml with an added comment line gives the same hash.
- `test_ruler_change_new_hash` — changing `metrics.cvr_auc.population` changes the hash.
- `test_run_block_not_hashed` — changing `run.budget.gpu_hours` leaves the hash unchanged.
- `test_missing_ruler_raises` — a yaml without `ruler` raises a clear `ValueError` naming the key.
- `test_nulls_allowed` — `aliccp.yaml` loads and hashes even with its seven nulls.

### Tests to pass — `tests/test_01_events.py`

- `test_first_line_is_run_started` — after `__init__` + `close`, the file has one line, type `run_started`, containing the protocol dict and hash.
- `test_concurrent_emit_no_torn_lines` — 3 threads × 1000 emits; file has 3001 lines; every line parses as JSON; seq is exactly 1…3001 with no gaps or repeats.
- `test_stamps_present` — every line has `schema_version==1`, `seq`, `t`, `run`, `protocol_hash`, `type`, `summary`.
- `test_unknown_type_raises` — `emit("failed", …)` raises; nothing is written.
- `test_bad_state_raises` — `emit("state_changed", state="failed", …)` raises.
- `test_missing_summary_raises`.
- `test_heartbeat_sidecar` — 10 heartbeats land in `heartbeat.jsonl`; `events.jsonl` line count is unchanged.
- `test_new_node_unique_under_threads` — 4 threads × 500 calls yield 2000 distinct ids.
- `test_close_drains_then_refuses` — line count after close equals emits + 1; emit after close raises.
- `test_seq_monotonic_same_millisecond` — 100 emits in a tight loop have strictly increasing seq even where `t` repeats.

### Gate to phase 2

All tests green. `python -m harness init protocols/synthetic.yaml` creates a run directory; `tail -f runs/<id>/events.jsonl` shows the `run_started` line with the hash printed by the command.

### Hands forward

The only write path to the log. Phase 2's fake run and every later module call `EventLog.emit` and nothing else.

---

## Phase 3 · Synthetic task and the candidate contract

**Owner** A: `tasks/synthetic.py`, `candidate/*`  
**Depends on** phase 1  
**Source** Backend_plan §5 contract, §10; Plan_delta §5 (seed rules)

### Goal

A generated dataset with the Ali-CCP funnel shape and four planted effects; a task adapter that owns the splits; a baseline training script that honours the harness–candidate contract; `report.py` and a seed `rules.jsonl` the step-7 semantic check will copy into each run.

### In scope

`harness/tasks/base.py`, `harness/tasks/synthetic.py`, `candidate/template.py`, `candidate/report.py`, `candidate/rules.jsonl`, `protocols/synthetic.yaml` (hash fields only), `tests/test_03_synthetic.py`, `tests/test_03_template.py`, this page.

### Out of scope

Ali-CCP anything. Spawning via `runner.py` (phase 4). Ladder / band / model-level Δ tests (phase 5). A model bigger than embedding(8) + MLP on CPU. Phase-10 rulebook R1–R6 (post-run checks) — keep distinct from C1–C7.

### Interfaces

```python
# harness/tasks/synthetic.py
def generate(seed, n_users=20_000, n_items=2_000, n_impressions=1_000_000) -> pa.Table
    # columns include f_true, f_marginal, f_zero, f_leak
class SyntheticTask:
    def prepare(protocol, root, *, seed=0) -> TaskPaths
    # candidate-visible: train.parquet, search_validation.parquet
    # harness_only/: holdout, generated.parquet, digests.json
    # script_sha = sha256(inspect.getsource(SyntheticTask.score))
    # candidate_env → exactly {TRAIN, VALID}

# candidate/report.py  (stdlib only; outside harness package)
# checkpoint.save(step, blob: bytes) — template serialises with torch first

# candidate/template.py  (a script; run as python template.py)
# import report  — never import harness.*
# report.result({}, preds_path=...)  — harness score() owns metrics
# SYNTHETIC_FAIL mid-training: crash|oom_* at step total//2; hang after first progress

# candidate/rules.jsonl — keys include mode: "forbid"|"require"
```

### Locked decisions (phase 3)

1. **Contract rules** — `candidate/rules.jsonl` with `mode`; C1 is `forbid` on VALID label reads.
2. **Hashes** — real sha256 in yaml; `prepare()` verifies non-placeholders; pin `pyarrow==25.0.1`; one `store_schema=False` write.
3. **`n_impressions`** — constructor arg only (default 1M); tests use 50K with placeholder hashes.
4. **AUC** — `sklearn.roc_auc_score` in `score()` only; template does not self-score.
5. **Baseline** — torch only; seeded permutation minibatches; progress/checkpoint ~10× per run.
6. **Four planted effects** — f_true ≈0.65, f_marginal ≈0.56 at 1M (clicked CVR AUC).
7. **Capability** — candidate scripts live under repo `candidate/`; runner copies into workspace.

### Tests to pass — `tests/test_03_synthetic.py`

- `test_deterministic`, `test_funnel_rates`, `test_leak_feature_auc`, `test_zero_feature_auc`
- `test_true_feature_auc` band `[0.60, 0.72]`, `test_marginal_feature_auc` band `[0.53, 0.60]`
- `test_splits_by_rule`, `test_candidate_env_has_no_holdout`, `test_score_populations`
- `test_score_hand_computed`, `test_seed_rules_parse` (asserts `mode`), `test_unseen_id_in_valid`

### Tests to pass — `tests/test_03_template.py` (50K-row synthetic)

- `test_contract_outputs`, `test_features_env_changes_model`, `test_seed_changes_result`
- `test_failure_modes_observable` (crash → exit 1), `test_report_imports_stdlib_only`
- `test_template_does_not_import_harness`, `test_runs_under_60s_cpu`

### Gate to phase 4

All tests green. Manual: run `python template.py` under env; harness `score()` fills AUCs; `SYNTHETIC_FAIL=oom_host` → returncode in `(-9, 137)`.

### Hands forward

Seven failure-mode fixtures (phase 4), four planted effects (phase 5), `score()` as the only numeric entry point, seed rules for step 7.

---

## Phase 4 · Runner

**Owner** A: `runner.py`  
**Depends on** phases 1, 3  
**Source** Backend_plan §5; Plan_delta §6 (policy); Handoff locked names

### Goal

Spawn the candidate as a child process, enforce a derived timeout, classify failures, recover per class (max 2 attempts), heartbeat, stall-watchdog, and return a `RunResult`. The runner trains nothing and decides nothing.

### In scope

`harness/runner.py`, `tests/test_04_runner.py`, this page; optional `fake_run.py` stall pair so the app sees the class.

### Out of scope

Which node to run next. Metric judgement (phase 5). SSH backend. Calibrating `seconds_per_row_screen`. Semantic check / `infra` / `llm_api` (phase 7). `LOADER_WORKERS` on the template.

### Interfaces

```python
FAILURE_CLASSES = (
    "cuda_oom", "host_oom", "diverged", "timeout",
    "contract_violation", "crash", "stall",
)
RECOVERY = {
  "cuda_oom": lambda env: {**env, "BATCH": str(int(env["BATCH"]) // 2)},
  "host_oom": lambda env: {**env, "BATCH": str(int(env["BATCH"]) // 2)},  # no LOADER_WORKERS
  "diverged": None,   # abandon; family note in failure summary
  "timeout": None,
  "contract_violation": None,
  "crash": None,
  "stall": lambda env: dict(env),  # retry once, no knob change
}

class LocalBackend:  # Popen; poll progress.jsonl every poll_s; stall + timeout kills
def derived_timeout(seconds_per_row_screen, rows, epochs, safety=2.0, floor_s=60) -> float
def classify(returncode, stderr_tail, progress, result_path, killed_as=None) -> str | None
    # NaN / loss>10×first → diverged
    # killed_as stall|timeout → that class
    # "CUDA out of memory" → cuda_oom
    # returncode in {-9,137} + empty stderr → host_oom (event returncode normalised to 137)
    # exit 0 + missing/invalid result.json → contract_violation
    # returncode != 0 → crash; else None

class Runner:
    def run(node, rung, seed, timeout_s, env_overrides={}, attempt=1) -> RunResult
        # metrics = task.score(preds, "search") on success — never child's self-report
```

### Locked decisions (phase 4)

1. **Names** — stub vocabulary + `stall`; not Plan_delta's `oom_gpu` / `nan_loss` / …
2. **Diverged** — abandon (no LR retry); summary carries `given_up:diverged` family note.
3. **host_oom** — `-9` and `137` equal; failure event stores `returncode=137`.
4. **Stall watchdog** — in the progress poll loop; threshold `max(5 min, 3× median step gap)` or `run_cfg["stall_threshold_s"]` override for tests.
5. **Attempt cap** — 2 in the runner; per-node cap 3 stays loop-level (phase 6).

### Tests to pass — `tests/test_04_runner.py` (synthetic 50K, `heartbeat_s=0.5`)

- `test_success_returns_scored_metrics`, `test_classify_table`, `test_timeout_kills_hang`
- `test_retry_on_cuda_oom`, `test_retry_on_host_oom`, `test_no_retry_on_contract_violation`
- `test_no_retry_on_diverged`, `test_max_two_attempts`, `test_heartbeats_written`
- `test_diverged_killed_early`, `test_stall_kills_and_retries`, `test_child_env_is_capability_safe`
- `test_derived_timeout`

### Gate to phase 5

All tests green. Manual: one real node through a real `EventLog`; watch heartbeat + failure/recovery in the app.

### Hands forward

`Runner.run` is the only way training happens. Phase 5 calibrates with it; phase 6 calls it per node; phase 7 tuner per trial.

---

## Phase 5 · Measurement

**Owner** A: `measure.py`  
**Depends on** phases 3, 4  
**Source** Build_phases `#p5` / Audit Redline §6 Ladder (27 Aug); Plan_delta §4 = no BH / DiD / bootstrap / Student-t only

### Goal

Everything that decides whether a number is believed: pure functions on numbers first, then `Measure` that emits verdicts. The synthetic scorecard must show zero false promotions, the planted true feature promoted, the marginal never *rejected*, and the planted leak caught — before any GPU hour is spent.

### In scope

`harness/measure.py`, `tests/test_05_measure_pure.py`, `tests/test_05_scorecard.py` (`@pytest.mark.slow`), event types `incumbent_changed` + `prediction`, this page, README Measurement line.

### Out of scope

Choosing the next node / queue / git workspace (phase 6). Attribution adjudication (phase 7 hands `attribution=` in). Phase-10 post-checks beyond `leak_audit`. BH, bootstrap CIs, Student-t tables, DiD. Smoke logic in `measure.py` (runner pass/fail only). Ali-CCP ingest.

### Interfaces

```python
# constants — each with a "# Redline §6 Ladder: …" comment
SIGMA_UNSTABLE, SCREEN_REJECT_DELTA, SCREEN_ADVANCE_SD, PROMOTE_FLOOR,
PROMOTE_Z_OVER_SQRT_K, REPLICATE_K, LEAK_TRIGGER_BANDS, LEAK_SINGLE_FEATURE_AUC,
LADDER_ETA, HOLDOUT_VISITS_MAX, HOLDOUT_SEEDS, INCONCLUSIVE_REVISITS,
INCONCLUSIVE_PRIORITY, RHO_REFRESH_AFTER, STALL_SD_MULT

@dataclass
class Band:
    sigma_screen, sigma_full, sigma_pair, ratio, rho
    sd_delta_screen, sd_delta_full, bar
    source: Literal["fixed_pair","refreshed"]; n_replicated: int

def calibrate(screen_per_seed, full_per_seed, fixed_seed_pair) -> Band
def refresh_rho(band, per_seed_deltas) -> Band
def screen_verdict(delta, band) -> Literal["rejected","replicating","inconclusive"]
def promote_bar(band) -> float
def replicate_verdict(deltas, band) -> Literal["pass","fail_sign","fail_mean"]
def leak_audit(mean_delta, band, single_feature_aucs) -> list[str]
def ladder_accepts(best_reported, new_holdout, eta=LADDER_ETA) -> bool
def inconclusive_next(prior_inconclusives) -> Literal["requeue","retire"]
def combine_inconclusive(a, b) -> Literal["re_measure"]  # never "pass"

class Measure:
    def calibrate_from_runs(self, runner, baseline_node, ...) -> Band
    def verdict(self, node, results, incumbent, rung, attribution=None) -> Verdict
    def holdout_report(self, node, runner, incumbent, best_reported) -> HoldoutReport
    def maybe_refresh(self) -> Band | None
```

Ladder: **smoke** (contract only, not in measure) → **screen** (one paired seed) → **replicate** (k=3 full, all Δ>0 and mean ≥ bar, attribution clear). **Holdout is not a rung** — ≤2 visits, candidate-side only; decides the *reported* number.

### Locked decisions (phase 5)

1. **Redline surface** — full `#p5` (screen + replicate + leak + attribution + holdout_report + ρ refresh). Plan_delta §4 only forbids BH / DiD / bootstrap / Student-t.
2. **Smoke** — no smoke logic in `measure.py`; `verdict()` raises `RungMismatch` on smoke.
3. **Constants** — never loosen a Redline constant to green the scorecard; retune planted weights only if pure tests pass and `f_true`/`f_marginal` miss.
4. **Events** — additive `incumbent_changed` and `prediction` (Plan_delta §1; no schema bump); `fake_run` covers both.
5. **False-promotion rate** — README + this page: ≈ 3% nominal (one-sided α = 0.05 × the fraction that reach replicate).

### Tests to pass — `tests/test_05_measure_pure.py`

`test_calibrate_columns`, `test_calibrate_unstable_raises`, `test_screen_table`, `test_promote_bar`, `test_replicate_k3`, `test_replicate_refuses_screen_rung`, `test_leak_trigger`, `test_attribution_gate`, `test_ladder_eta`, `test_holdout_budget`, `test_holdout_candidate_side_only`, `test_inconclusive_revisits`, `test_inconclusive_never_stacks`, `test_verdict_pairs_by_seed`, `test_rho_refresh`, `test_verdict_emits_event`.

### Tests to pass — `tests/test_05_scorecard.py` (`slow`, ~200K)

`test_baseline_calibrates`, `test_zero_feature_not_promoted`, `test_true_feature_promoted`, `test_marginal_feature_not_rejected`, `test_leak_feature_trips`, `test_holdout_never_in_ladder`, `test_scorecard_printed` → `FP=0 FN=0 marginal=<promoted|inconclusive> leak=caught`.

### Gate to phase 6

Pure tests green; slow scorecard prints `FP=0 FN=0 … leak=caught`. Calibration `Band` visible as a `measurement` event in the app. Nominal false-promotion rate recorded in README.

### Hands forward

Phase 6 calls `Measure.verdict` after every screen/replicate batch and `holdout_report` at most twice per run. The state a node moves to is decided here and only here.

