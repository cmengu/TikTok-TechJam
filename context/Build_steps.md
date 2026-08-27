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

A generated dataset with the Ali-CCP funnel shape and three planted effects; a task adapter that owns the splits; a baseline training script that honours the harness–candidate contract; `report.py` and a seed `rules.jsonl` the step-7 semantic check will copy into each run.

### In scope

`harness/tasks/base.py`, `harness/tasks/synthetic.py`, `harness/candidate/template.py`, `harness/candidate/report.py`, `harness/candidate/rules.jsonl`, `protocols/synthetic.yaml` (hash fields only), `tests/test_03_synthetic.py`, `tests/test_03_template.py`, this page.

### Out of scope

Ali-CCP anything. Spawning via `runner.py` (phase 4). Ladder / band / model-level Δ tests (phase 5). A model bigger than embedding(8) + MLP on CPU. Phase-10 rulebook R1–R6 (post-run checks) — keep distinct from C1–C7.

### Interfaces

```python
# harness/tasks/base.py — Task Protocol + TaskPaths (already stubbed)

# harness/tasks/synthetic.py
def generate(seed, n_users=20_000, n_items=2_000, n_impressions=1_000_000) -> pa.Table
    # columns: sample_id, user_id, item_id, cat_a/b/c, hist, click, conversion,
    #          f_true, f_zero, f_leak
class SyntheticTask:
    def __init__(self, n_impressions: int = 1_000_000): ...
    # prepare writes parquet (compression="zstd", no metadata); sha256s each file;
    # raises on mismatch when yaml hash is non-placeholder; script_sha of this file
    # candidate_env → exactly {TRAIN, VALID}; never holdout
FAILURE_ENV = "SYNTHETIC_FAIL"

# harness/candidate/report.py  (stdlib only)
# WORKSPACE env: progress.jsonl, result.json, checkpoints/step-N.pt (last 3)

# harness/candidate/template.py  (torch + pyarrow + numpy + report)
# env: DEVICE, SEED, TRAIN, VALID, FEATURES, BATCH, LR, EPOCHS, WORKSPACE
# base features = user_id,item_id,cat_a,cat_b,cat_c (hist excluded v1)
# SYNTHETIC_FAIL: crash|oom_cuda|oom_host|nan|hang|no_result|bad_schema

# harness/candidate/rules.jsonl — one JSON object per line, keys:
#   id, statement, check ("static"|"llm"), pattern (regex|null),
#   severity ("fail"|"warn"), source ("seed" | later "node NNN")
```

### Locked decisions (phase 3)

1. **Contract rules** — seed file `harness/candidate/rules.jsonl` (shape shared with `runs/<id>/rules.jsonl`); seven C-clauses from Plan_delta; not CONTRACT.md; not R1–R6.
2. **Hashes** — real sha256 in yaml; `prepare()` verifies non-placeholders; pin `pyarrow==25.0.1`; write `compression="zstd"`, no user metadata; `script_sha` = sha256 of `synthetic.py`.
3. **`n_impressions`** — constructor arg only (default 1M); tests use 50K with placeholder hashes in the protocol copy.
4. **AUC** — `sklearn.roc_auc_score` in `score()`; hand-rolled only in `test_score_hand_computed`.
5. **Baseline** — torch only; seeded permutation minibatches (no DataLoader); dropout param present, value 0.
6. **`score()`** — join preds↔labels on `sample_id`; assert id sets equal.
7. **`oom_host`** — assert returncode in `(-9, 137)`; hang via `Popen`, poll 3s, kill in `finally`.
8. **Checkpoints** — `torch.save(state_dict)`; keep last 3 by step.

### Tests to pass — `tests/test_03_synthetic.py`

- `test_deterministic`, `test_funnel_rates`, `test_leak_feature_auc`, `test_zero_feature_auc`, `test_true_feature_auc`
- `test_splits_by_rule`, `test_candidate_env_has_no_holdout`, `test_score_populations`
- `test_score_hand_computed`, `test_seed_rules_parse`, `test_unseen_id_in_valid`
- hash mismatch raises when yaml is filled (covered via prepare)

### Tests to pass — `tests/test_03_template.py` (50K-row synthetic)

- `test_contract_outputs`, `test_features_env_changes_model`, `test_seed_changes_result`
- `test_failure_modes_observable`, `test_report_imports_stdlib_only`, `test_runs_under_60s_cpu`
- checkpoints ≤ 3 files

### Gate to phase 4

All tests green. Manual: run the template under env and read the two AUCs; `SYNTHETIC_FAIL=oom_host` → returncode in `(-9, 137)`.

### Hands forward

Seven failure-mode fixtures (phase 4), three planted effects (phase 5), `score()` as the only numeric entry point, seed rules for step 7.
