# Handoff — Phase 5 (measurement) · 27 Aug

You are picking up after Phase 4. Planning is frozen; do not re-open it.
Decisions that are still open go in the Phase-5 PR description, not in a new
plan doc. **Read this page first. Do not execute code until you have confirmed
the ladder-scope lock with the human (see §Conflicts below) — Plan_delta §4
“minimal-first” vs Build_phases Redline ladder.**

## Read these, in this order

1. This file.
2. `context/Plan_delta.md` — §1 schema growth; §4 minimal-first ladder note
   (may conflict with Build_phases — confirm before coding); §2 ranking is
   out of scope until phase 6.
3. `context/Backend_plan.md` §6 — measurement / noise / ladder intent (older;
   where it fights the Redline, the Redline wins once locked).
4. `context/Build_phases.html` §Phase 5 (`#p5`) — **interfaces, constants,
   named tests, gate.** This is the detailed build page until you write the
   Phase-5 page into `Build_steps.md`.
5. `context/Build_steps.md` — Phase 1 is the page format. Write the **Phase 5**
   page in that format in the same PR; never write Phase 6+ ahead.

## Current state (merged to main)

Confirm with `git log origin/main --oneline -8`. As of this handoff:

- **Phases 0–4 on main**, including:
  - Phase-3 review fix (`fix/phase-3-review` / PR #8): four planted effects,
    capability-safe `candidate/` at repo root, mid-training fails.
  - Phase 4 runner + `run-one` CLI + app event-log / follow-newest-run.
- **Open / not required for Phase 5:** `fix/phase-2-review` (SSE partial-line,
  runs-path, fake-wipe, lastSeq) — independent; do not block on it.

### What you inherit

| Area | Location | Notes |
|---|---|---|
| Synthetic task | `harness/tasks/synthetic.py` | Four planted cols: `f_true`≈0.65, `f_marginal`≈0.56, `f_zero`, `f_leak` (1M, clicked CVR AUC). `harness_only/` for holdout + digests. `score()` is the only numeric authority; rejects duplicate `sample_id`. |
| Candidate | `candidate/template.py`, `candidate/report.py`, `candidate/rules.jsonl` | Outside harness package. `import report`; `report.result({}, preds_path=…)`; checkpoints = bytes. Runner **copies** both into workspace and runs `[python, "template.py"]`. |
| Runner | `harness/runner.py` | `LocalBackend`, classify/recover/stall, `Runner.run` → `RunResult` with `task.score` metrics. |
| Events | `harness/events.py` | Emit `measurement` / `verdict` / `rule_trip`; no invented states. |
| Stub | `harness/measure.py` | **Outdated stub** (old `Band` shape). Replace to match Build_phases `#p5`, do not implement the stub’s fields as-is. |
| Tests | `pytest` from repo root (`.venv`) | Default: `addopts = -m 'not slow'`. Scorecard is `@pytest.mark.slow`. |

App watch: `python -m app.server` / `python -m harness.fake_run` / `python -m harness run-one …`.

## What to build now — Phase 5 only

| File | Role |
|---|---|
| `harness/measure.py` | Constants, pure fns, `Band`, `Measure` (calibrate / verdict / holdout_report / maybe_refresh) |
| `tests/test_05_measure_pure.py` | Named pure tests from Build_phases `#p5` |
| `tests/test_05_scorecard.py` | `@pytest.mark.slow` — real runner, ~200K synthetic |
| `context/Build_steps.md` | Phase-5 page (Phase-1 format) |

Extend `IMPLEMENTED` with `"harness.measure"` in this PR.

**Out of scope:** choosing the next node / queue / git workspace (phase 6);
attribution *adjudication* logic that invents labels (phase 7 hands
`attribution=` in — measure only gates on it); phase-10 post-check rulebook;
BH / bootstrap / Student-t / DiD (removed 27 Aug — do not reintroduce);
Ali-CCP / ingest (phase 8); rewriting runner or planted-effect *bars*
(if scorecard fails, retune phase-3 **weights**, never loosen constants).

### Interfaces (from Build_phases `#p5` — implement these)

```python
# constants — each with a "# Redline §6 Ladder: …" comment
SIGMA_UNSTABLE, SCREEN_REJECT_DELTA, SCREEN_ADVANCE_SD, PROMOTE_FLOOR,
PROMOTE_Z_OVER_SQRT_K, REPLICATE_K, LEAK_TRIGGER_BANDS, LEAK_SINGLE_FEATURE_AUC,
LADDER_ETA, HOLDOUT_VISITS_MAX, HOLDOUT_SEEDS, INCONCLUSIVE_REVISITS,
INCONCLUSIVE_PRIORITY, RHO_REFRESH_AFTER, STALL_SD_MULT

@dataclass
class Band:
    sigma_screen, sigma_full, sigma_fix, ratio, rho
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

Ladder in one line: **smoke** (contract only) → **screen** (one paired seed) →
**replicate** (k=3 full, all Δ>0 and mean ≥ bar, attribution clear). **Holdout
is not a rung** — run-level, ≤2 visits, candidate-side only; decides the
*reported* number, never the incumbent.

### Named tests

**Pure — `tests/test_05_measure_pure.py`** (σ_screen=0.015, σ_full=0.012 unless stated):
`test_calibrate_columns`, `test_calibrate_unstable_raises`, `test_screen_table`,
`test_promote_bar`, `test_replicate_k3`, `test_replicate_refuses_screen_rung`,
`test_leak_trigger`, `test_attribution_gate`, `test_ladder_eta`,
`test_holdout_budget`, `test_holdout_candidate_side_only`,
`test_inconclusive_revisits`, `test_inconclusive_never_stacks`,
`test_verdict_pairs_by_seed`, `test_rho_refresh`, `test_verdict_emits_event`.

**Slow scorecard — `tests/test_05_scorecard.py`** (real runner, ~200K synthetic):
`test_baseline_calibrates`, `test_zero_feature_not_promoted`,
`test_true_feature_promoted` (`FEATURES=base,f_true`, attribution clear),
`test_marginal_feature_not_rejected` (`base,f_marginal` → promoted|inconclusive, never rejected),
`test_leak_feature_trips`, `test_holdout_never_in_ladder` (scorecard path emits
zero holdout measurements), `test_scorecard_printed`
(`FP=0 FN=0 marginal=<…> leak=caught`).

### Gate

Pure tests green; slow scorecard prints `FP=0 FN=0 … leak=caught`. Calibration
`Band` visible as a `measurement` event in the app. Record nominal false-promotion
rate (~3%) in README as the gate page asks. If scorecard fails: fix planted
size in phase 3 or arithmetic here — **never loosen a Redline constant**.

## Conflicts to resolve with the human BEFORE coding

| Topic | Plan_delta §4 | Build_phases `#p5` (Redline 27 Aug) |
|---|---|---|
| Scope | “rung-0 band, reject-only screen, k=3 → promising”; defer holdout/DiD confirm, BH, … | Full Redline: screen + replicate + leak + attribution gate + `holdout_report` (≤2) + ρ refresh |
| Stub `Band` | n/a | New fields (`sigma_screen`/`sigma_full`/…); **delete** old stub shape |
| Holdout | Deferred as confirm *rung* | Not a rung; run-level budgeted visit — still in Phase 5 API |

**Recommended default to propose:** implement the **Redline / Build_phases `#p5`**
surface (pure tests + scorecard). Treat Plan_delta §4 as “no BH / no DiD /
no bootstrap” (already absent from `#p5`), not as permission to drop
`holdout_report` or leak/attribution. Do not invent a third ladder.

Also honour locks from prior phases:

- Metrics only from `task.score` / `RunResult.metrics` — never child self-report.
- Capability: never put holdout / `harness_only` / `protocols/` on the child env;
  candidate scripts stay under repo `candidate/` and are copied into workspace.
- Failure class names stay stub vocabulary (`cuda_oom`, …, `stall`) — measure
  does not reclassify runner failures.
- Planted bands are locked: if `f_true` fails promote or `f_marginal` is
  rejected, retune weights in synthetic generate — **never** widen test bands
  or lower `PROMOTE_FLOOR`.

## Working rules

- Branch `phase-5-measure` off **updated main** (with PR #8 already merged),
  green → PR. Never stack on an unmerged fix branch.
- Event log is the only seam; `verdict` / `measurement` / `rule_trip` /
  `incumbent_changed` as specified; no node state `"failed"`.
- Pure functions first; `Measure` only wraps them + emits. Fake runner for
  holdout budget / seed-pairing tests; real runner only in `@pytest.mark.slow`
  scorecard.
- CPU only; synthetic task only. Extend `fake_run.py` only if new event fields
  must show in the app before a real calibrate.
- `pytest` skips `slow` by default; run scorecard explicitly:
  `pytest tests/test_05_scorecard.py -m slow`.

## What NOT to do

- Do not start Phase-6 Build_steps / `tree.py`.
- Do not reintroduce BH, bootstrap CIs, Student-t tables, or DiD.
- Do not loosen Redline constants or planted-effect AUC bands to green the
  scorecard.
- Do not put holdout paths in `candidate_env` or teach the child to score.
- Do not “helpfully” rename failure classes or implement phase-7 attribution
  LLM — accept `attribution=` as an argument.

## Hands forward after Phase 5

Phase 6 calls `Measure.verdict` after every screen/replicate batch and
`holdout_report` at most twice per run. The state a node moves to is decided
here and only here. Phase 7 later supplies real attribution labels; phase 10
adds post-check rules beyond leak_audit.
