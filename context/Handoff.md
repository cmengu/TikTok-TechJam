# Handoff — Phase 4 (runner) · 27 Aug

You are picking up after Phase 3. Planning is frozen; do not re-open it.
Decisions that are still open go in the Phase-4 PR description, not in a new
plan doc. **Classifier / retry naming is LOCKED (see §Locked below). Do not
re-ask; implement against that table.**

## Read these, in this order

1. This file.
2. `context/Plan_delta.md` — overrides anything that conflicts with it.
   Phase 4 is bound by §6 (typed retry table, classifier priority, watchdog,
   never-wedge). Schema growth rule is §1. **Names** follow the lock below,
   not Plan_delta's vocabulary.
3. `context/Backend_plan.md` §5 — runner semantics (subprocess, timeout,
   heartbeat, contract).
4. `context/Build_steps.md` — Phase 1 is the page format. Write the **Phase 4**
   page in that format in the same PR; never write Phase 5+ ahead.
5. Frozen Phase-4 interface (also summarised below) lives in the build-phases
   artifact / prior agent notes: `harness/runner.py` stubs + tests in
   `tests/test_04_runner.py`.

## Current state

- **Merged to main (confirm with `git log origin/main`):** phases 0–2 (+ docs
  build-plan). **Phase 3 may still be on `phase-3-synthetic-template` —
  merge it to main before branching `phase-4-runner`. Never stack Phase 4 on
  the unmerged Phase 3 branch.**
- Phase 3 delivered (inherit after merge):
  - `harness/tasks/synthetic.py` — generate / prepare / score / rows;
    `n_impressions` constructor arg (default 1M); tests use 50K + placeholder
    protocol copy; filled `protocols/synthetic.yaml` hashes verified in
    `prepare()` when non-placeholder.
  - `harness/candidate/template.py` — torch baseline; env
    `DEVICE,SEED,TRAIN,VALID,FEATURES,BATCH,LR,EPOCHS,WORKSPACE`; seven
    `SYNTHETIC_FAIL` modes: `crash|oom_cuda|oom_host|nan|hang|no_result|bad_schema`.
    Manual seeded permutation (no DataLoader) — do **not** add `LOADER_WORKERS`.
  - `harness/candidate/report.py` — stdlib-only top-level imports;
    `progress.jsonl`, `result.json` (atomic tmp+rename), checkpoints last-3.
  - `harness/candidate/rules.jsonl` — seed C1–C7 (step-7 copies to
    `runs/<id>/rules.jsonl`). **Not** phase-10 R1–R6.
- Stubs still raise under `tests/test_00_skeleton.py`; extend `IMPLEMENTED`
  with `"harness.runner"` in the Phase-4 PR.
- Tests: `pytest` from repo root (venv: `.venv`). App watch:
  `python -m app.server` / `python -m harness.fake_run`.

## What to build now — Phase 4 only

| File | Role |
|---|---|
| `harness/runner.py` | `LocalBackend`, `derived_timeout`, `classify`, `Runner.run` |
| `tests/test_04_runner.py` | named tests below |
| `context/Build_steps.md` | Phase-4 page (Phase-1 format) |

**Out of scope:** choosing the next node; judging metrics (phase 5); SSH
backend; calibrating `seconds_per_row_screen` (formula only — inputs passed in);
semantic check (phase 7); `types.py` unless you must and you say so in the PR;
`infra` / `llm_api` failure classes (phase 7).

### Locked — classifier / retry (27 Aug, human)

Keep stub **names**. Plan_delta **policy** where it differs. Add `stall` as an
extra class (not a rename). Do not invent a third vocabulary.

```python
FAILURE_CLASSES = (
    "cuda_oom", "host_oom", "diverged", "timeout",
    "contract_violation", "crash", "stall",
)

# RECOVERY (None = abandon / no runner retry):
#   cuda_oom            → BATCH // 2, retry once
#   host_oom            → BATCH // 2, retry once   # same knob; no LOADER_WORKERS
#   diverged            → None (abandon); family note in failure summary
#   timeout             → None (abandon)
#   contract_violation  → None (coder path later; no runner retry)
#   crash               → None (coder debug later)
#   stall               → retry once (no knob change)

# classify priority (deterministic-first):
#   NaN / loss>10×first in progress → diverged
#   "CUDA out of memory" in stderr  → cuda_oom
#   returncode in {-9, 137} + empty/no useful stderr → host_oom
#     (normalise returncode to 137 on the failure event)
#   stall: last progress older than max(5 min, 3× median step gap)
#     → kill, class stall
#   killed at derived deadline → timeout
#   exit 0 + missing/invalid result.json → contract_violation
#   returncode != 0 → crash
#   else None (success path)

# Runner.run: env = DEVICE/SEED/WORKSPACE/BATCH/LR/EPOCHS/FEATURES
#   + task.candidate_env + overrides; score via task.score(preds,"search") on success;
#   metrics from harness score(), never the child's self-reported numbers.
# Stall watchdog lives in LocalBackend's 1s progress.jsonl poll loop.
# Runner attempt cap = 2 (per-node cap 3 is loop-level, phase 6).
```

### Named tests — `tests/test_04_runner.py` (synthetic 50K, `heartbeat_s=0.5`)

- `test_success_returns_scored_metrics`
- `test_classify_table` — seven `SYNTHETIC_FAIL` → expected class
  (`no_result`/`bad_schema` → `contract_violation`)
- `test_timeout_kills_hang` — `timeout_s=3`, done within 5s, no orphan
- `test_retry_on_cuda_oom` — fake backend fails once then ok; BATCH halved; attempt=2
- `test_retry_on_host_oom` — BATCH halved (same recovery as cuda_oom)
- `test_no_retry_on_contract_violation`
- `test_no_retry_on_diverged` — abandon; summary carries family note
- `test_max_two_attempts`
- `test_heartbeats_written` — ≥3 heartbeats with node + step
- `test_diverged_killed_early`
- `test_stall_kills_and_retries` — tiny threshold override + `heartbeat_s=0.5`
  so the watchdog fires in seconds
- `test_child_env_is_capability_safe` — no holdout / `protocols/` / rulebook in
  env keys or values; child `PYTHONPATH` must not expose harness package root
- `test_derived_timeout` — formula + floor

### Gate

All tests green. Manual: one real node through a real `EventLog`; watch
heartbeat + failure/recovery in the app.

## Phase-3 locks Phase 4 must honour

- `oom_host`: child may exit `-9` or `137`; classifier → `host_oom`, event
  returncode normalised to `137`.
- Child writes `result.json` atomically (already true in `report.result`).
- `score()` is the only numeric entry; runner must call `task.score`.
- Capability: `candidate_env` is only `{TRAIN, VALID}`; do not pass holdout.
- No `LOADER_WORKERS` on the template (no DataLoader).

## Working rules (unchanged)

- Branch `phase-4-runner` off **updated main** (with Phase 3 merged), green → PR.
- Event log is the only seam; emit `failure` / `recovery` / `heartbeat`; do not
  invent node state `"failed"` — use `debugging` + `failure` event.
- Retries = new attempt with counted cost; nothing edited retroactively.
- Extend `fake_run.py` only if you add event types/fields the app must see
  (e.g. `stall` if the app must see it before a real run).
- CPU only; synthetic task only.

## What NOT to do

- Do not touch Ali-CCP / ingest (step 8).
- Do not implement `measure.py` ladder (step 5) in this PR.
- Do not start Phase-5 Build_steps page.
- Do not rename `FAILURE_CLASSES` to Plan_delta names (`oom_gpu`, `nan_loss`, …).
- Do not add `infra` / `llm_api` yet (phase 7).
- Do not add `LOADER_WORKERS` to the template.

## Hands forward after Phase 4

`Runner.run` is the only way training happens. Phase 5 calls it to calibrate
the band and run the synthetic scorecard; Phase 6 calls it per node; Phase 7
tuner calls it per trial.
