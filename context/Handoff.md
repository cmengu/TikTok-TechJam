# Handoff — Phase 7 (agents) · 28 Aug

You are picking up after Phase 6. Planning is frozen; do not re-open it.
Decisions that are still open go in the Phase-7 PR description, not in a new
plan doc. **Read this page first.**

## Read these, in this order

1. This file.
2. `context/Plan_delta.md` — §2 ranking arithmetic (queue score from verdict
   events; LLM never writes priority); §3 crash recovery = replay (`Tree.rebuild`
   shipped in phase 6; `resume` CLI still deferred).
3. `context/Backend_plan.md` §5 (Optuna) and §8 (agents / brief / cache).
4. `context/Build_phases.html` §Phase 7 (`#p7`) — **interfaces, named tests,
   gate.** Detailed build page until you write the Phase-7 page into
   `Build_steps.md`.
5. `context/Build_steps.md` — Phase 6 page is done. Write the **Phase 7** page
   in that format in the same PR; never write Phase 8+ ahead.
6. Skim `harness/tree.py` + `harness/__main__.py` — Phase 7 **swaps** the coder
   and queue source; it does not rewrite the ladder or measure.

## Current state

Confirm with `git log origin/main --oneline -8`. As of this handoff:

- **Phases 0–5 on main** (measure, runner, synthetic, events, app shell).
- **Phase 6 on branch `phase-6-tree` / PR #12** — merge (or rebase onto updated
  `main`) before starting phase 7. Includes:
  - `harness/tree.py` — `TRANSITIONS`, `Workspace`, `Queue`, `family_stats`,
    `Tree.step` / `run`, `rebuild()` fold.
  - `harness/__main__.py` — `python -m harness run …` (no `resume` verb).
  - `hypotheses/hand.yaml` + `hypotheses/patches/*.diff` (five FEATURES patches).
  - `tests/test_06_tree.py` (15 unit) + `tests/test_06_loop.py` (`slow`).
  - App: `incumbent_changed` → `state.incumbent`; Incumbent panel on dashboard.
  - `IMPLEMENTED` includes `"harness.tree"`.
- **Uncommitted fixes on `phase-6-tree` (commit before merge or fold into PR
  #12):**
  - `Workspace.commit_node` resolves repo-relative patch paths before `git apply`
    (hand.yaml paths like `hypotheses/patches/base.diff` — apply cwd is
    `runs/<id>/workspace`, not repo root).
  - `app/server.py` — `Cache-Control: no-store` on `/` (stale cached
    `index.html` without `#view` caused `Cannot set properties of null`).
  - `app/static/app.js` — `requireView()` guard with a clear error message.

### What you inherit

| Area | Location | Notes |
|---|---|---|
| Tree loop | `harness/tree.py` | Greedy + fork-on-stall, lessons file, `Coder` seam. **Do not rewrite** except passing `LLMCoder` and a queue-refill hook. Seeds locked **1,2,3** (`SCREEN_SEED=1`, `FULL_SEEDS=(1,2,3)`). |
| Measure | `harness/measure.py` | Still owns verdicts. Phase 7 **adjudicates** `attribution=` (hand loop used `"clear"`). |
| Runner | `harness/runner.py` | `run_cfg["candidate_src"]` points at git workspace after phase 6. |
| Hand demo | `hypotheses/hand.yaml` | Fallback demo; keep working. Phase 7 adds LLM path alongside. |
| Agent stubs | `harness/agents/*.py` | `LLM`, `FakeLLM`, `LLMCoder`, `propose`, `tune`, `brief`, `cache` — all raise. |
| CLI | `harness/__main__.py` | `run` wires hand.yaml today; phase 7 adds researcher + real coder path. |
| Tests | `pytest` from repo root (`.venv`) | `harness.agents` in skeleton `IMPLEMENTED` set already; extend per module as you ship. |

App watch:

```bash
python -m app.server
python -m harness run protocols/synthetic.yaml --hypotheses hypotheses/hand.yaml
# open: http://127.0.0.1:8000/?run=<run_id>#/dashboard
```

**Hard-refresh** (Cmd+Shift+R) if the UI is blank — old cached HTML has no `#view`.

## What to build now — Phase 7 only

| File | Role |
|---|---|
| `harness/agents/llm.py` | `LLM` protocol, `FakeLLM`, adapters, `log_usage` |
| `harness/agents/researcher.py` | `propose()` — schema-validated `Hypothesis`, bank + lessons |
| `harness/agents/coder.py` | `LLMCoder` — unified diff, apply retry, capability-safe prompt |
| `harness/agents/tuner.py` | Optuna screen-rung tuner → shortlist of knob hyps |
| `harness/agents/brief.py` | `compose()` — deterministic brief from organisers text |
| `harness/agents/cache.py` | Query cache keyed by normalised query + protocol_hash |
| `hypotheses/bank.yaml` | Seeded bank (feature-side first, expected gains) |
| `tests/test_07_agents.py` | Named tests — **FakeLLM only**, no network |
| `tests/test_07_tuner.py` | Named tuner tests — fake runner |
| `context/Build_steps.md` | Phase-7 page (Phase-1 format) |

Wire into `harness run` (or a thin flag): swap `PatchCoder` → `LLMCoder`, fill
queue from `propose()` instead of (or after) `hand.yaml`. **Minimal `tree.py`
changes** — coder injection + queue-refill hook only.

Extend `IMPLEMENTED` with `harness.agents` (and submodules as they land) in this PR.

**Out of scope:** network calls in tests; tuning on any rung but screen; more
than six knobs; Optuna dashboard / Terminator / multi-objective; Ali-CCP ingest
(phase 8); `harness resume` (still deferred — `Tree.rebuild` exists); MCTS /
bandit; loosening Redline constants; large `tree.py` refactors.

### Interfaces (from Build_phases `#p7` — implement these)

```python
# llm.py
class LLM(Protocol):
    def complete(self, role: str, prompt: str, schema: dict | None) -> tuple[Any, Usage]
class FakeLLM:  # scripted per role; raises if exhausted
def log_usage(events, node, slice, usage) -> None

HYPOTHESIS_SCHEMA = {stage ∈ Stage, mechanism: slug, description,
                     citation | "no prior", expected_gain, expected_gpu_h}

# researcher.py
def propose(llm, brief, incumbent_summary, family_stats, lessons, cache) -> Hypothesis | None

# coder.py
class LLMCoder(Coder):
    def materialise(self, hyp, incumbent, traceback) -> Path
    # prompt: hyp + template source + traceback only — no holdout/protocol paths
    # git apply fail → one retry with apply error as traceback

# tuner.py  (optuna==4.9.*)
def tune(node, knob_space, runner, events, budget, screen_seed) -> list[Hypothesis]
    # trial nodes kind="trial"; screen rung only; top-3 shortlist, never promoted
```

### Named tests

**`tests/test_07_agents.py` (FakeLLM):**  
`test_valid_proposal_becomes_hypothesis`, `test_missing_expected_gain_rejected`,
`test_bad_stage_rejected`, `test_bank_seeds_first_proposals`,
`test_research_events_emitted`, `test_coder_applies_diff`,
`test_coder_retries_on_apply_failure`, `test_coder_prompt_capability`,
`test_cache_hit_same_hash_miss_other_hash`, `test_brief_deterministic`.

**`tests/test_07_tuner.py` (fake runner):**  
`test_converges`, `test_trial_events`, `test_incumbent_first`,
`test_shortlist_not_promoted`, `test_failed_trial_marked`,
`test_small_budget_no_study`.

### Gate

All tests green. Manual: one real LLM smoke call per role (not in tests), then
loop on synthetic with real researcher for ~three nodes; Research events with
token costs visible in the app.

## Carried locks (do not re-open)

| Topic | Decision |
|---|---|
| Seeds | **1,2,3** everywhere (screen paired seed **1**). `#p6`'s `0,1,2` is stale. |
| `resume` CLI | **Still deferred.** `Tree.rebuild(events)` exists; no `orphaned` class yet. |
| Queue priority | `family_stats` arithmetic only; LLM never writes priority. |
| Attribution | Phase 7 owns adjudication; pass real `attribution=` into `Measure.verdict`. |
| Capability | Coder/researcher prompts never see holdout, `protocols/`, `measure.py`, rulebook. |
| Patch paths | Diffs may be repo-relative in yaml; `Workspace.commit_node` must resolve to `REPO_ROOT` before `git apply`. |

## Operational notes (from phase-6 demo runs)

1. **CLI:** one line — `--hypotheses` must be on the same line as its value:
   ```bash
   python -m harness run protocols/synthetic.yaml --hypotheses hypotheses/hand.yaml
   ```
2. **Calibrate is slow** (~minutes on 200K CPU) before the tree dequeues nodes;
   events stall after `node_created` baseline + `hypothesis_queued` lines — normal.
3. **Frontend blank / `innerHTML` null:** browser cached pre-shell `index.html`
   (no `#view`). Hard-refresh; ensure server serves current `app/static/index.html`.
4. **`git apply` patch not found:** fixed by resolving paths in `commit_node`; ensure
   that fix is merged before relying on hand patches in a fresh run.
5. **Record a green demo run id** after slow loop passes — judges' fallback.

## Working rules

- Branch `phase-7-agents` off **updated main** (with phase 6 merged), green → PR.
- All agent tests use `FakeLLM` / fake runner — no network in pytest.
- Real LLM adapters are thin; smoke manually once per role before demo.
- Event log is the only seam; additive types OK (Plan_delta §1).
- Do not change `tree.py` beyond coder swap + queue-refill hook.

## What NOT to do

- Do not implement `harness resume` or `"orphaned"` in this PR.
- Do not retune Redline measure constants or planted AUC bands.
- Do not put holdout in child env or teach the candidate to score.
- Do not implement MCTS, UCT, bandit, or ensembling.
- Do not have the LLM write queue priorities that bypass `family_stats`.
- Do not start phase 8 Ali-CCP ingest.

## Hands forward after Phase 7

Phase 8 swaps the **task** (`AliCCPTask`) under an unchanged loop. Phase 9 adds
convergence ε/N stop. A later PR may add `resume` on top of `Tree.rebuild`.
