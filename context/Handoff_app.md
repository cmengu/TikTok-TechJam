# Handoff — App batch 1 (entrypoint · reducer · Protocol page) · 27 Aug

Owner: **Yan, frontend lane.** This batch touches only `app/` and
`app/static/`. Everything else in the repo is read-only for this work.

Planning is frozen. Three tasks, in order, one branch. Do not widen scope;
the parked list below is deliberate and was agreed with the teammate.

## Read these, in this order

1. This file.
2. `app/static/reducer.js`, `app/static/app.js`, `app/static/index.html` —
   what exists today.
3. `harness/types.py` — `EVENT_TYPES` (16) and `STATES` (9). This is the
   vocabulary. Never invent a member of either.
4. `harness/events.py` — the envelope stamped on every line, and the shape of
   the `protocol` object embedded in `run_started`.
5. `harness/fake_run.py` — the scripted stream you develop against.
6. `harness/runner.py` — the **real** `heartbeat` / `failure` / `recovery`
   field shapes. They are richer than `fake_run`'s. The reducer must tolerate
   both without special-casing either.
7. `app/static/reducer.test.js` and `tests/fixtures/fake-events.jsonl` — the
   existing test harness. Extend it; do not replace it.

## Environment

Python 3.12 venv at `.venv`, must be activated in every new shell:

```
source .venv/bin/activate
python --version          # must print 3.12.x
python -m pytest
node --test "app/static/*.test.js"   # the bare directory form does not work; see below
```

Two terminals for the manual gate, each with its own `source`:

```
python -m harness fake --speed 20
python -m app
```

zsh notes that have cost time before: no `#` comments on the interactive
command line; `hash -r` if a stale binary path is cached; always
`python -m pytest`, never bare `pytest`.

---

## Task 1 — make the documented run command true

`app/server.py` defines `app = FastAPI()` and nothing else. There is no
uvicorn entrypoint, so `python -m app.server` imports the module, exits 0, and
never listens. `context/Handoff.md` documents that exact command, so the docs
are currently wrong rather than the code being merely incomplete.

Add **both** entrypoints so either spelling works:

- `app/__main__.py` — calls
  `uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=True)`.
  Makes `python -m app` work.
- An `if __name__ == "__main__":` guard at the bottom of `app/server.py` doing
  the same. Makes the documented `python -m app.server` work.

Use the import-string form (`"app.server:app"`), not the object, so `reload`
works. Add a `python -m app` line to `README.md`. Note in the PR description
that `context/Handoff.md`'s app-watch command was broken, so the teammate can
correct it in his own doc — do not edit his file.

---

## Task 2 — rewrite `reducer.js`  ← the real work

### The problem

`harness/types.py` declares 16 event types. The current reducer has a `case`
for 7. The other 9 (`measurement`, `failure`, `recovery`, `rule_trip`,
`research_source`, `cache_lookup`, `submission_written`, `intervention`,
`run_ended`) fall through to `default: break` and survive only as raw lines in
`state.log`.

Worse, it discards fields on events it *does* handle:

- `run_started` carries the entire protocol object (`ruler` + `run`). The
  reducer keeps `{id, protocol_hash, task}` and bins the rest. That object is
  the whole Protocol page — Task 3 is blocked until this stops.
- `node_created` carries `hypothesis_id`. Dropped. There is currently no link
  between a queue row and the node it became.
- `verdict` carries `band`. Dropped. The product spec's hardest rule for the
  Run tab is "no bare numbers anywhere; every score with its noise band" —
  unenforceable while the band is thrown away.

### Known bugs to fix while you are in here

1. **`lastSeq` is corrupted by heartbeats.** `events.jsonl` and
   `heartbeat.jsonl` have *independent* sequence counters (see
   `EventLog._event_seq` vs `_heartbeat_seq`). `reduce()` sets
   `lastSeq: ev.seq` unconditionally, so a heartbeat rewinds it. Harmless
   today only because `app.js` tracks its own two cursors. Track
   `lastSeq` and `lastHeartbeatSeq` separately.
2. **`queue_reordered` silently deletes.**
   `(ev.order || []).map(...).filter(Boolean)` drops any hypothesis not named
   in `order`. If the backend ever reorders a subset, rows vanish with no
   error. Unnamed entries must keep their relative order and be appended
   after the named ones.
3. **The log will drown.** `fake_run` emits ~90 `measurement` ticks for node 3
   alone. `state.log` keeps the last 200 events indiscriminately, so a
   "last five events" panel would be five score ticks every time. Keep the
   raw log, and add a separate significance-filtered `feed`.

### The state contract

Implement exactly this shape. It is the seam every later screen builds on, so
field names matter more than internals.

```js
export const initial = () => ({
  lastSeq: 0,
  lastHeartbeatSeq: 0,

  run: {
    id: null,
    task: null,
    protocolHash: null,
    protocol: null,      // FULL run_started.protocol object — do not prune
    startedAt: null,     // run_started.t
    endedAt: null,       // run_ended.t
    endReason: null,     // run_ended.reason
    status: "waiting",   // "waiting" | "running" | "ended"
  },

  nodes: {},        // id -> NodeView
  nodeOrder: [],    // creation order, for stable rendering

  queue: [],        // ordered QueueEntry[]

  workers: {},      // worker -> latest raw heartbeat event

  verdicts: [],           // raw, in order
  measurements: [],       // raw, capped at 500 (not rendered yet; kept for later)

  research: {
    sources: [],          // raw research_source events, deduped by id
    lookups: [],          // raw cache_lookup events
    hits: 0, misses: 0, confirmed: 0, contradicted: 0,
  },

  reliability: {
    failures: [], recoveries: [], ruleTrips: [],
    failuresByClass: {},    // failure class -> count
    recoveriesByClass: {},  // failure class -> count
    ruleTripsByRule: {},    // rule id -> count
  },

  submissions: [],    // raw submission_written events
  interventions: [],  // raw intervention events

  log: [],      // every non-heartbeat event, capped 500
  feed: [],     // significance-filtered, capped 50
  unknown: {},  // unrecognised ev.type -> count
});
```

```js
// NodeView
{
  id, parent, kind,
  hypothesisId,      // from node_created.hypothesis_id — MUST be kept
  state,             // one of STATES; "screening" at creation
  stateHistory: [],  // [{ state, seq, t }]
  scores: {},        // metric -> number[], parallel to seeds
  seeds: [],
  bands: {},         // metric -> [lo, hi], latest band per metric — MUST be kept
  latestVerdict: null,
  failures: [], recoveries: [], ruleTrips: [],
  createdSeq,
}

// QueueEntry
{
  id, stage, mechanism, parentNode,
  position,       // 0-based, current
  prevPosition,   // position before the last queue_reordered; null if never moved
  movement,       // prevPosition - position; positive = moved up; 0 if unchanged
  queuedSeq,
  nodeId,         // set when a node_created names this hypothesis_id; else null
  started,        // nodeId != null
}
```

### Rules

- **Duplicate events must be ignored, per stream.** First two lines of
  `reduce`:

  ```js
  if (ev.type === "heartbeat" && ev.seq <= state.lastHeartbeatSeq) return state;
  if (ev.type !== "heartbeat" && ev.seq <= state.lastSeq) return state;
  ```

  Without this, `hits`/`misses`, `failuresByClass`, queue entries and node
  `scores`/`seeds` double-count on any replay. Today the `?since=` transport
  prevents duplicates, but that guarantee lives in `app.js` and `server.py`,
  not in the module that owns state — and the Report screen ("the same renderer
  fed a finished run") will eventually fold an array into a non-empty state.
- **Purity is non-negotiable.** `reduce(state, ev)` returns a new object and
  mutates nothing reachable from `state`. No DOM, no `fetch`, no `Date.now()`,
  no imports beyond the module itself. It must stay runnable under
  `node --test` with no browser and no Python.
- **Never throw on input.** An unrecognised `ev.type` increments
  `unknown[type]` and is still appended to `log`. The schema will grow
  (`schema_version` exists for exactly this reason); the app must degrade, not
  crash.
- **Never drop an unknown field.** `log` holds the raw event. Projections on
  top of it may be selective; the log may not.
- **Heartbeats** update `workers[ev.worker]` and `lastHeartbeatSeq` only.
  They never enter `log` or `feed`.
- **`feed` includes:** `run_started`, `node_created`, `state_changed`,
  `verdict`, `failure`, `recovery`, `rule_trip`, `hypothesis_queued`,
  `queue_reordered`, `submission_written`, `intervention`, `run_ended`.
  (`hypothesis_queued` was missing from an earlier draft of this list — it IS
  feed-worthy. A new hypothesis is the only visible output of the researcher
  agent, and Innovation is judged on what the agent chose to try. The startup
  burst of six is a rendering concern — collapse consecutive same-type rows in
  the view — not a reducer concern.)
  **Excludes:** `measurement`, `heartbeat`, `research_source`, `cache_lookup`
  — papers get their own ticker on the Dashboard later, per the product spec.
- **`state` values** are validated against the nine in `harness/types.py`. An
  unknown state is recorded and counted in `unknown`, not assigned to a node.
- **`cache_lookup`**: `hit === true` increments `hits` else `misses`;
  `confirmed === true` increments `confirmed`, `confirmed === false`
  increments `contradicted`, `undefined` increments neither.
- **`research_source`**: dedupe by `id`; last write wins.

---

## Task 3 — app shell + Protocol page

### Why Protocol first

Product spec puts it in first position deliberately, and the truncation order
in `beating-nise-knowledge.md` §6 is `log format → Protocol → header strip`.
It is also the only spec section whose data is 100% present in the stream
today — all of it is in `run_started.protocol`.

### The shell

Minimal hash router, **vanilla JS, no framework, no build step.** Rationale:
this batch adds one page; committing to a framework now would be deciding on
the least information we will ever have. Revisit before the Run tree and node
dossier, which is where vanilla DOM actually starts to hurt.

- Sidebar, in spec order: `Dashboard · Protocol · Brief · Research ·
  Hypotheses · Run · Audit (Replication / Cost / Reliability) · Report`.
- Routes via `location.hash` (`#/protocol`), default `#/dashboard`.
- **Live now:** `Protocol` (new, real) and `Dashboard` (the existing
  four-panel view, moved as-is and labelled provisional in a code comment).
- **Every other route** renders a one-line "not built yet" stub. Do not
  scaffold their contents.
- Leave an empty `<header>` element with named slots for the header strip
  (run state · submission light · spend · interventions · elapsed/budget) but
  **do not populate it** — that is the next batch and part of it is parked.
- The SSE plumbing in `app.js` is good. Keep it. Do not rewrite the
  reconnect-with-`since` logic or the newest-run poller.
- Refactor `render()` so each route owns its own render function reading from
  reduced state. No route may read from an `EventSource` directly.
- Keep everything renderable from a plain array of events as well as from a
  live stream — the Report screen is later specified as "the same renderer fed
  a finished run", and retrofitting that is expensive. Concretely: the entry
  point takes a source, and nothing below it knows which one it got.

### Protocol page contents

All from `state.run.protocol`. Read-only. Nothing on this page may change a
run — per spec, every control that could is an intervention.

Two visually distinct tiers, and this distinction is load-bearing:

**Hashed (`ruler`)** — defines comparability:
- `rulebook_version`, `protocol_hash`, `schema_version`, `protocol_path`, `task`
- **Data** — `ingest_hash`; `train` and `test` each `{source, sha256}`
- **Splits** — `search_validation`, `holdout_validation`, each
  `{from, rule, sha256}`
- **Metrics** — a table: metric · population · positive label · required
  output. (`cvr_auc` requiring `p_conversion_given_click` is the field a
  submission bug would hide behind; make it prominent.)
- **Scoring** — `script_sha`, `aggregation`
- **Baseline** — `repo`, `commit`, `command`, `published {ctr_auc, cvr_auc}`,
  `reproduced` five seeds per metric. Render `reproduced` as `[min, max]` plus
  the range, not five loose numbers — the spread *is* the noise band and it is
  the point of the block.
- **Convergence** — `epsilon`, `n_rounds`
- **Seeds** — `pinned` list, `cuda_deterministic`

**Not hashed (`run`)** — bounds a run, never comparability. Visually separated
with an explicit label saying so:
- `budget {gpu_hours, wall_clock_h, llm_usd}`, `workers`

Rules for this page:

- **`null` renders as an explicit chip**, e.g. `not set — filled from the
  28 Aug webinar`. Never blank. `protocols/aliccp.yaml` is mostly nulls right
  now and a blank cell is indistinguishable from a rendering bug.
- **Hashes render truncated to 12 chars, monospaced, click-to-copy full.**
- Before `run_started` arrives, the page shows a waiting state, not an error.
- Develop against `protocols/synthetic.yaml`, which is fully populated; check
  it also renders sanely against `protocols/aliccp.yaml`'s nulls.

---

## Explicitly parked — do NOT build

Agreed with the teammate; these land in a later phase.

- **Anything cost or spend related.** No event emits a `cost` field. Do not
  invent one, do not add it to `fake_run.py`, do not build Audit → Cost, do
  not populate the header's spend slot.
- **`rung` on verdicts, and Audit → Replication.** Same reason.
- **The Brief screen.** No events exist and the spec already names it the
  designated cut.
- Dashboard redesign, Research, Hypotheses redesign, Run tree redesign, node
  dossier, Audit → Reliability, Report. The reducer must *hold* the data for
  these (it does, per the contract above) but no screen is built for them.

---

## Tests

Extend `app/static/reducer.test.js`.

**Do NOT regenerate `tests/fixtures/fake-events.jsonl`.** Treat it as an input
you verify, not an artefact you rebuild. Two reasons:

1. It is a *generated* file that both people regenerate. Two regenerations of
   the same 115-line generated file is a guaranteed merge conflict with no
   meaningful resolution.
2. Its first line embeds `protocol_path` as an **absolute path from whoever
   generated it** (currently `/Users/ngchenmeng/beating-nise/...`). Regenerating
   locally rewrites every line's `protocol_hash` and that path, producing a
   diff that looks like a real change and is not one.

**Heartbeats need a SECOND fixture.** `heartbeat` will never appear in
`fake-events.jsonl` — heartbeats go to the sidecar `heartbeat.jsonl` by design
(the app opens two SSE streams for exactly this reason). A single-file fixture
therefore cannot reach 16/16, and `test_heartbeat_does_not_touch_lastSeq` and
`test_heartbeat_excluded_from_log_and_feed` would pass vacuously against a
corpus with zero heartbeats.

Add `tests/fixtures/fake-heartbeats.jsonl`, generated once from a
`python -m harness fake --instant` run directory. Generating this one IS
allowed, and does not contradict the rule above: `main` does not have the file
so there is nothing to conflict with, and `EventLog.heartbeat()` stamps no
`protocol` object, so the file contains no absolute path and no machine-specific
churn. Never overwrite `fake-events.jsonl` while doing it.

The coverage test then asserts: the 15 non-heartbeat types appear in
`fake-events.jsonl`, and `heartbeat` appears in `fake-heartbeats.jsonl`.
Together that is 16/16.

Instead, add a test that *asserts* the fixture exercises all 16 types in
`EVENT_TYPES` and reports the per-type counts. If a type is missing, stop and
report it rather than regenerating. (The machine-specific `protocol_path` is
worth raising with the teammate as a separate fix — the harness should emit a
repo-relative path — but that is `harness/events.py`, not our lane. Record it
in the notes file, do not fix it here.)

Named tests, all fixture-driven, no Python at run time:

- `test_all_event_types_reduce_without_throwing`
- `test_reduce_is_pure` — deep-freeze the input state, assert no mutation
- `test_protocol_object_retained_whole`
- `test_node_keeps_hypothesis_id`
- `test_verdict_band_retained_per_metric`
- `test_scores_and_seeds_stay_parallel`
- `test_queue_reorder_preserves_unnamed_entries`
- `test_queue_movement_tracked`
- `test_queue_entry_links_to_node`
- `test_failure_and_recovery_counted_by_class`
- `test_rule_trip_counted_by_rule`
- `test_research_sources_deduped_by_id`
- `test_cache_lookup_tallies`
- `test_submission_and_intervention_recorded`
- `test_run_lifecycle_status` — waiting → running → ended with reason
- `test_heartbeat_does_not_touch_lastSeq`
- `test_heartbeat_excluded_from_log_and_feed`
- `test_feed_excludes_measurement_ticks`
- `test_unknown_event_type_is_counted_not_thrown`
- `test_replay_is_idempotent` — **corrected spec.** Folding the fixture twice
  from `initial()` is tautologically true for a deterministic pure function and
  tests nothing. The real property is duplicate tolerance:
  `fold(fold(initial, events), events)` must deep-equal `fold(initial, events)`.
  Test that, and make it pass with the per-stream seq guard above — not by
  weakening the assertion
- `test_event_vocabulary_matches_python` — read `harness/types.py` as TEXT,
  regex out the `EVENT_TYPES` and `STATES` tuples, assert they match the arrays
  hand-copied at the top of `reducer.js`. No Python execution, no dependency.
  The reducer stays pure; the *test* is allowed file IO. `types.py` is the
  two-person seam, so silent drift between it and the JS copy must be a red
  test rather than a rendering mystery

Keep existing tests passing unchanged where the contract has not moved.

## Gate

- `python -m pytest` green.
- `node --test "app/static/*.test.js"` green. **Use this spelling.** Passing a
  bare directory (`node --test app/static/` or `app/static`) fails with
  `Cannot find module .../app/static` — Node treats the directory argument as
  an entry file instead of scanning it. Reproduced on Node 22.23 and 24.x, and
  on `main` before this branch, so it is pre-existing and unrelated to our
  changes. Note it in the PR description.
- `python -m app` and `python -m app.server` both serve on 8000.
- Manual: `python -m harness fake --speed 20` in one terminal, browser in the
  other. Protocol page fills in the instant `run_started` lands; the existing
  four panels behave exactly as before; sidebar routes without a page reload;
  a browser refresh mid-stream reproduces the same state.

## Before every commit — fetch and rebase

`main` moves while this branch is open; the teammate merges phase PRs through
the day. Before every commit on `app-batch-1`:

```
git fetch origin
git log --oneline HEAD..origin/main          # what landed since we branched
git diff --name-only HEAD...origin/main -- harness/types.py harness/events.py \
    harness/fake_run.py app/ tests/fixtures/
```

That second command is the one that matters: those are the only paths on `main`
that can invalidate work in this batch. If it prints nothing, the reducer
contract is intact and you can proceed.

Then commit your work **first**, and rebase after — never stash a dirty tree
across a rebase:

```
git add -A && git commit -m "..."
git rebase origin/main
python -m pytest && node --test "app/static/*.test.js"    # re-run AFTER the rebase
```

If the rebase conflicts on `tests/fixtures/fake-events.jsonl`, take `main`'s
version wholesale (`git checkout --theirs` during rebase) — see the fixture
rule under Tests.

## Branch and PR

Branch `app-batch-1` off updated `main`. Three commits, one per task, in
order. Green before PR. PR description states: the `python -m app.server` bug
found in `context/Handoff.md`, the two reducer bugs fixed, and the parked list
so the teammate can see what was deliberately left.

## What NOT to do

- Do not touch `harness/measure.py`, `harness/tree.py`, `harness/agents/`,
  `harness/outputs.py`, `harness/audit.py` — teammate's lane.
- Do not touch `harness/types.py`. If you believe it needs a change, stop and
  say so in the PR description instead.
- Do not edit `context/Handoff.md` — it is the teammate's phase doc.
- Do not extend `fake_run.py` in this batch.
- Do not add a frontend framework, bundler, or npm dependency.
- Do not add `localStorage` or any browser storage.
- Do not add a control that changes a run. Every such control is an
  intervention, and interventions are 20% of the grade.
- Do not download or touch Ali-CCP (step 8).

---

# Handoff — App batch 2 (header strip · Dashboard) · 27 Aug

Batch 1 is merged/open as PR #9. Branch `app-batch-2` off updated `main` once
#9 lands; if it has not landed, branch off `app-batch-1` and say so in the PR.

**Framework decision, now settled: stay vanilla.** No framework, no bundler, no
npm dependency. Revisit only if batch 3 (Run tree + node dossier) proves it
necessary. Adopting one now would mean rewriting the shell and Protocol page.

Everything below reads from reduced state. The reducer does not change in this
batch. If you believe it must, stop and say so rather than editing it.

## Task 4 — header strip

Populate the `<header id="header-strip">` slots left empty in batch 1. Visible
on every route. Five slots, four of them live:

| Slot | Source |
|---|---|
| Run state | `state.run.status` (`waiting`/`running`/`ended`) + `state.run.endReason` when ended |
| Submission written | `state.submissions.length > 0` → green "submission written"; zero → amber "no submission yet" |
| Spend | **PARKED.** Render a dimmed `—` with a `title` saying spend is not yet instrumented. Do not invent a number, do not compute one from anything |
| Interventions | `state.interventions.length` |
| Elapsed vs budget | `state.run.startedAt` → now, against `state.run.protocol.run.budget.wall_clock_h` |

Notes:

- **Elapsed needs a clock, and the reducer has none by design** (it is pure —
  no `Date.now()`). The view owns the ticking: one `setInterval` at 1s that
  re-renders only the header, never the route. Freeze it at `endedAt` once
  `status === "ended"`.
- Budget may be `null` (aliccp until the webinar). Show elapsed alone with a
  "no budget set" chip rather than dividing by null.
- Submission written is a *light*, not a count. `submission_written` carries
  only `{node, path, summary}` — no validity field; validation is the
  teammate's phase 9/10 and does not exist in the stream yet. The header
  reports what happened (a file was written), not a verdict on it. The green
  state's `title` says so explicitly: "written from a promoted node; not
  validated — rulebook post-checks are not instrumented yet".
- The header is not a control panel. Nothing in it is clickable except, if you
  like, a link to the route that explains it.

## Task 5 — Dashboard

Replace the provisional four-panel view. Per the product spec, the Dashboard
answers four questions in five seconds: **is it alive, what's it doing, how far
along, is anything wrong.** Five panels:

1. **Now running** — one panel per worker from `state.workers`. Status, node,
   step/total, loss, attempt. A worker whose latest heartbeat is stale should
   look stale (the heartbeat's `t` vs now, same clock as the header).
2. **Score against baseline** — the incumbent's latest promoted scores per
   metric, each **with its noise band**, against
   `protocol.ruler.baseline.published` and the `reproduced` spread. The
   number and its band are always shown — never delete the reading, never
   compute or override the verdict. `band` means opposite things depending on
   which verdict produced it (see `harness/measure.py`): for
   `inconclusive`/`rejected` (screening), inside the band means no signal —
   grey it. For `replicating`/`promoted` (replication), inside the band means
   the replicate agreed — render it normally. The verdict badge is always
   `ev.state` verbatim; the app reports the harness's verdict, it never
   invents one.
3. **Last five events** — from `state.feed`, newest first. `inconclusive` must
   appear as its own event kind, never folded into `rejected`. Collapse
   consecutive same-type rows (the six startup `hypothesis_queued` events
   should be one row saying so, not six).
4. **Progress toward stopping** — `protocol.ruler.convergence` (`epsilon`,
   `n_rounds`) plus verdicts since the last `promoted` verdict. **Label this
   "derived in the app" explicitly**: the harness is specified to emit a
   convergence counter on every verdict (`outputs.py`, phase 9) and does not
   yet. When that event arrives, this panel switches to it. Do not present a
   derived number as if the harness reported it.
5. **Paper ticker** — titles from `state.research.sources`, ticking past. Titles
   only here; the Research tab is where a paper is attached to the hypothesis
   it produced. Show cache hit/miss tallies from `state.research` beside it.

**Nothing on the Dashboard changes the run.** Every control that could is an
intervention, and interventions are 20% of the grade.

## Out of scope for batch 2

Run tree redesign, node dossier, Research, Hypotheses, Audit, Report, and
everything on the batch-1 parked list (cost/spend, `rung` on verdicts, Brief).

## Gate

- `python -m pytest` and `node --test "app/static/*.test.js"` green.
- Real browser, not the DOM shim: `python -m harness fake --speed 20` +
  `python -m app`, look at it.
- Confirm: header visible on every route and updates live; elapsed ticks
  without re-rendering the route; spend slot dimmed, not fabricated; all five
  Dashboard panels populate; no bare score without a band; inconclusive renders
  grey and labelled; a mid-stream refresh reproduces the same state; zero
  console errors.
- Pre-commit sync as always.

---

# Handoff — App batch 3 (band contract · Run tree · node dossier) · 28 Aug

Branch `app-batch-3`, cut from `app-batch-2` because PR #11 had not merged
when batch 3 opened. Once #11 lands, batch 3's base is already contained in
`main` — do not rebase.

**Framework decision holds: stay vanilla.** Batch 3 was the agreed revisit
point. The Run tree does not force a framework: the reducer already holds
the full node graph, and the tree is a recursive render over it.

## What PR #10 changed underneath us

The teammate's real `harness/measure.py` landed mid-batch-2 and invalidated
the batch-2 band model:

- A verdict's `band` is now a **dict** (`_band_payload` is `asdict(Band)`,
  `measure.py:120-121`). The new `Band` has no `lo`/`hi` at all — it carries
  `sigma_screen`, `sigma_full`, `sigma_pair`, `ratio`, `rho`,
  `sd_delta_screen`, `sd_delta_full`, `bar`, `source`, `n_replicated`
  (`measure.py:51-61`).
- **Nothing tests containment.** `screen_verdict` compares a delta to
  `SCREEN_ADVANCE_SD * sd_delta_screen` (`:194`); `replicate_verdict`
  compares a mean delta to `promote_bar(band)` (`:214`). The inside/outside
  model from batch 2 was a `fake_run.py` artefact.
- Verdicts now carry `rung`, `delta_mean` and `delta_per_seed`
  (`:428-442`). `rung` was parked by agreement in batch 1; the harness has
  unparked it.
- Two additive event types exist: `incumbent_changed` and `prediction`
  (`harness/types.py:41-42`). The reducer handles both.
- `harness/fake_run.py` still emits the old `[lo, hi]` pair and no `rung`.
  It is the teammate's file. He has been asked to update it. The app must
  work correctly either way, and must not be edited to assume he has.

## The band contract — settled, do not re-litigate

`app/static/band.js` is a pure module (no DOM, no `app.js` imports). It is
the only place that interprets a band. Nothing else may parse `band`.

`readBand(raw)` returns one of three shapes and never throws:

| shape | when | fields |
|---|---|---|
| `measure` | non-null, non-array object | the raw dict |
| `legacy` | array of exactly two finite numbers | `{lo, hi}` |
| `none` | anything else, including null/undefined | `null` |

`verdictReading(verdict)` returns
`{shape, value, valueKind, threshold, thresholdLabel, side, rung}`.

Three rules, each of which cost us a bug to learn:

1. **Discriminate on `rung`, never on `state`.** The harness branches on
   `rung` (`measure.py:364`, `:371`) and puts it in the payload (`:433`).
   State does not invert: `replicating` is a *screen* outcome (`:369`);
   `rejected` comes from both rungs (`:369`, `:406`, `:409`);
   `inconclusive` comes from both (`:369`, `:399`).
2. **A missing rung is not a guess.** A dict band with no `rung` means "we
   do not know which comparison the harness made". `threshold` stays null.
   Same rule as spend and vs-baseline significance: a visible gap beats a
   plausible number.
3. **`legacy` and `none` never get a threshold.** `lo`/`hi` are not
   something `screen_verdict` or `promote_bar` compared against.

Two sync tests guard the contract and will fail loudly if the teammate
changes the harness: `test_band_fields_match_python` (against `class Band`)
and `test_screen_advance_sd_matches_python` (against `SCREEN_ADVANCE_SD`).

Boundary note: the harness advances on `>=` (`:194`) and fails on `<`
(`:214`), so a value exactly at the threshold **passes** in both
directions. `side` reports `at` as its own value; the view decides.

## Task 6 — wire the Score panel to band.js

`renderScoreCell` still gates on `Array.isArray(verdict.band) && length === 2`.
Against a real verdict that is false, so it falls through to a bare number
with no band and no annotation — a silent failure of the rule the panel
exists to enforce.

- Replace the inline band parsing with `verdictReading`. Delete `app.js`'s
  own `verdictBandTest` once nothing calls it.
- **The Incumbent cell still shows a score, not a delta.** The column
  answers "where does the incumbent stand against the published
  baseline" — a score question. `delta_mean` answers "did this node beat
  the *previous incumbent*" — a different question, and it belongs in the
  node dossier.
- When `threshold` is present, annotate the cell with the harness's own
  comparison, e.g. `Δ +0.015 ≥ bar 0.012`. Use `thresholdLabel` verbatim.
- When `threshold` is null, say which comparison is unavailable and why
  (legacy band / no rung). Never grey a verdict for a missing threshold.
- **Do not grey a promoted verdict.** That was batch 2's bug and the new
  model makes it structural: a promoted verdict is a replicate pass, which
  by definition cleared the bar.

## Task 7 — Run tree

The reducer already holds everything. Do not change it.

`state.nodes` is keyed by node id, each carrying `parent`, `kind`,
`hypothesisId`, `state`, `stateHistory`, `scores`, `seeds`, `bands`,
`latestVerdict`, `failures`, `recoveries`, `ruleTrips`, `createdSeq`.
`state.nodeOrder` is creation order. `state.incumbent` is the current
incumbent's node id.

- Recursive render over `parent`. Roots are nodes with `parent === null`.
- Each node shows id, hypothesis id, kind, and its state **verbatim from
  `ev.state`**. The app reports the harness's verdict; it never computes,
  renames or infers one. Never reuse `inconclusive` as a display word for
  anything but the state of that name.
- Mark the incumbent from `state.incumbent`, not by scanning verdicts.
- A node with no parent link and no known parent id is an orphan — render
  it at the root with a marker, do not drop it. Dropping data silently was
  the `queue_reordered` bug in batch 1.
- Nodes are selectable; selection drives the dossier. Route as
  `#/run/<nodeId>`. An unknown id renders "no such node", not a blank page.
- Per-route render key as established in batch 1: selecting a node must not
  re-render the whole app.

## Task 8 — node dossier

The panel beside the tree, for the selected node. Everything from
`state.nodes[id]` plus that node's verdicts filtered out of `state.verdicts`.

- Full state history from `stateHistory`, with seq and time.
- Every verdict for the node, newest first, each run through
  `verdictReading`: the delta, the threshold it was measured against, the
  label, and which side. This is where `delta_mean` and `delta_per_seed`
  belong.
- `rung` per verdict, shown plainly. It is no longer parked.
- Failures, recoveries and rule trips from the node's own arrays.
- Scores and seeds per metric.
- If `attribution` or `rule_trips` are present on a verdict, show them —
  a leak trip is the most important thing a node can carry.

## Out of scope for batch 3

Research, Hypotheses, Audit, Report, the Brief screen, and cost/spend.
`harness/fake_run.py` and every other file under `harness/` — not our lane.

## Gate

- `python -m pytest` and `node --test "app/static/*.test.js"` green.
- **Real browser, hard-reloaded.** `python -m harness fake --speed 2` +
  `python -m app`, then **Cmd+Shift+R** — a plain reload serves cached JS
  and will show you the previous build's behaviour. This cost us a full
  round trip in batch 3.
- Console open, zero errors.
- Confirm: the tree renders all three fake-stream nodes with the right
  parentage; the incumbent is marked; selecting a node fills the dossier
  and does not re-render the route; the Score panel shows a band annotation
  or an explicit reason there is none, and never a bare number; a
  mid-stream refresh reproduces the same state.
- Smoke test is a standing step, not a one-off. Batch 2 shipped three bugs
  that 27 passing tests never touched; all three surfaced within ten
  minutes of running it.

---

# Handoff — App batch 4 (visual design) · 28 Aug

Branch `app-style-1`, cut from `app-batch-3` at `62d9744`. Visual design only.
**No new features. No behaviour changes. No markup changes except where a task
below says so explicitly.**

## Reference

The target is Harvey's product UI, established from screenshots by sampling
pixels — not from memory. Five moves carry the look:

1. **One dark rail, everything else pale.** Full-height sidebar at `#0f0e0c`.
   It is the only large dark area and does most of the work.
2. **Two surfaces, not five.** Warm off-white canvas `#f7f5f4`, pure white
   panels `#ffffff`. That value step *is* the panel edge.
3. **Near-invisible borders, and no shadows anywhere.** A panel edge in the
   reference steps `#f7f5f4 → #f5f3f1 → #ffffff` over three pixels.
4. **Desaturated, dark colour.** Positive green samples `#396b53`. Nothing is
   bright. Status chips keep a neutral fill with coloured ink and a coloured dot.
5. **Serif appears twice only** — wordmark and page title. Everything else sans.

## Tokens — the complete set

Light mode only. `color-scheme: light` stays. There is deliberately no
`prefers-color-scheme` block and no `data-theme` stamping in this app.

```
--canvas:      #f7f5f4      --ink:         #1a1917
--surface:     #ffffff      --ink-muted:   #6a6866
--sunken:      #f1efec      --ink-faint:   #9d9a96
--hairline:    #e8e5e1
--hairline-hi: #d9d5d0
--rail:        #0f0e0c      --rail-ink:    #b8b5b1
--rail-raised: #33312d      --rail-ink-hi: #ffffff
--rail-hover:  #1e1d1a      --rail-ink-dim: #73716e

--pos:  #396b53   --pos-wash:  #eef3f0
--warn: #8a6a2c   --warn-wash: #f6f1e6
--crit: #96323c   --crit-wash: #f9edee
--info: #3e4e7d   --info-wash: #eef0f6

--r-panel: 10px   --r-ctl: 8px
--s1: 4px  --s2: 8px  --s3: 12px  --s4: 16px
--s5: 24px --s6: 32px --s7: 48px
```

## Type

Self-hosted from `app/static/fonts/`, declared with `@font-face` and
`font-display: swap`. No CDN link, no network dependency at demo time.

- **Instrument Serif** — display only: app wordmark and page title. Nothing else.
- **Instrument Sans** — everything else.

Display roles carry `transform: scaleX(1.06)` with `display: inline-block` and
`transform-origin: left center`. This is deliberate: Instrument Serif reads too
narrow at these sizes. 1.06 is the agreed value; it is a distortion, so do not
raise it without asking.

Scale: 44 / 27 display · 17 / 15 / 13 / 11 sans. Line-height 1.55 body,
1.15 display. Eyebrow labels are 11px, uppercase, `letter-spacing: .09em`.

The 2.75rem display size in the type scale has no element in the app. `h1`
is the sidebar wordmark at 1.5rem. If a page title is ever added it is a
markup change and needs its own checkpoint.

**Every number rendered from the stream gets `font-variant-numeric: tabular-nums`**
so live values stop jittering as digits change.

## Space, edges, motion

| Rule | Value |
|---|---|
| Space scale | 4·8·12·16·24·32·48. Nothing off-scale. |
| Panel padding | 24 |
| Grid gap | 16 |
| Content max width | 1400px, gutter 32 |
| Rail width | 228px, nav row height 36 |
| Radius | 10 panel / 8 control / 999 pill |
| Border | 1px `--hairline`, one weight everywhere |
| Shadows | **None. Anywhere.** |
| Motion | 120ms ease-out on nav, hover, focus. 160ms fade on route change. |
| Motion — never | No transition on any value that comes off the stream. |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` collapses all to 0ms. |

The three-stop body gradient is removed. The ground is one flat `--canvas`.

## Honesty rules, restated as design rules

These are not stylistic. They existed before this batch and they outrank it.

1. **Every state word on screen is the harness's own, verbatim.** Styling never
   renames, recolours into a different meaning, or hides one.
2. **A rule trip stays the loudest thing on the screen.** It is the only element
   in the system permitted both a tinted fill (`--crit-wash`) and a 3px left
   stripe (`--crit`). Loudness is carried by form as well as hue, so it survives
   greyscale and a bad projector.
3. **Every other state is a neutral panel with coloured ink and a coloured dot.**
   Fill stays `--surface`.
4. **A visible gap is a feature.** Spend, vs-baseline significance and
   "no threshold available" get a shared grammar: dashed border, italic,
   `--ink-faint`. They must read as *intentionally empty*. They may look better.
   They may not disappear, and they may never be filled with a plausible number.

## Checkpoint plan

- **0 — ground.** Branch, fonts, this brief. No CSS.
- **1 — tokens and primitives.** Add the `:root` block and `@font-face`. Replace
  all 34 hardcoded colour literals with `var(--…)`. Apply type scale, space
  scale, flat canvas, dark rail. Restyle the header strip. No markup changes.
- **2 — Dashboard**, five panels.
- **3 — Protocol**, two tiers.
- **4 — Run**, tree plus dossier.
- **5 — sidebar, empty states, and the gap grammar audited across all screens.**

## Out of scope for batch 4

- Brief, Research, Hypotheses, Audit's three children, Report — still stubs, not
  worth styling.
- `reducer.js`, `band.js`, `tree.js`, `dossier.js` — pure and tested. Do not touch.
- Any harness file.
- Framework, build step, CSS preprocessor, second stylesheet. All CSS stays in
  the single `<style>` block in `index.html`.

## Gate

Every checkpoint smoke-tests in a real browser before commit, hard-reloaded with
Cmd+Shift+R. Two terminals, each with its own `source .venv/bin/activate`:

```
python -m harness fake --speed 2
python -m app
```

Plus `node --test "app/static/*.test.js"` and `python -m pytest` green.

## Known: webfont subset gaps

The latin subsets of Instrument Sans and Instrument Serif do not contain
`Δ` (U+0394) or `⚠` (U+26A0). Verified by reading the cmap of all three
woff2 files. app.js currently renders `Δ` 3 times and `⚠` 2 times; both fall
back to a system font, and on macOS `⚠` may render as a colour emoji.
Deferred to a later checkpoint, where app.js is in scope. Do not fix it by
swapping the character, adding a CDN font, or hiding the glyph.

## Contrast floor

Measured on the real palette, not estimated.

`--ink-faint` (#9d9a96) is 2.58:1 on `--canvas` and 2.80:1 on `--surface`.
It is a decorative mark colour only — separators and rules. It must never
carry text.

Any text that carries meaning uses `--ink-muted` (5.11:1) or darker. This
binds especially on:
  - the three deliberate gaps — spend, vs-baseline significance,
    "no threshold available". A gap that is technically present but sits
    below 3:1 has half-disappeared, which is the thing the honesty rule
    exists to prevent.
  - any harness state word rendered verbatim.

Reference values on `--canvas`: --ink 16.16:1, --ink-muted 5.11:1,
--pos 5.68:1. On their washes: --crit 6.52:1, --warn 4.46:1.
On `--rail`: --rail-ink 9.45:1, --rail-ink-dim 3.97:1 (non-interactive
group labels only), --rail-ink-hi 19.29:1.

The near-invisible hairline (--hairline at 1.16:1 on canvas) is intended.
Panel separation comes from the surface value step, not the border.

## Dead selectors removed

`.score-above`, `.score-below` and `.score-inconclusive` were removed at
checkpoint 2a. They styled nothing: `renderScoreCell` (app/static/app.js:126)
emits only `score-value` and `band-note`, and by design the Score panel never
greys a promoted verdict — every row reaching it has already cleared the bar
(app.js:116-119). If per-verdict greying is ever wanted in this panel it is
an app.js change with its own checkpoint, not a CSS revival.

The Score panel spans two grid tracks above 1100px. That selector is coupled
to renderDashboard's section order; if the panel order changes, the selector
must change with it.

## Dashed means provisional

Dashed edges are a single grammar across the app, not a decoration:

  - the three deliberate gaps — spend, vs-baseline significance,
    "no threshold available" — dashed border, italic, --ink-muted
  - the not-hashed protocol tier — dashed left stripe, --warn
  - an orphan node in the Run tree — dashed border, --crit

All of them mean "this is provisional, absent, or not binding". Solid edges
mean the opposite. Anything new that is genuinely provisional should be
dashed; nothing else should be.

This also gives the Protocol screen's hashed/not-hashed split a second cue
beyond hue, so it survives greyscale, a projector, and colour-vision
deficiency. Checkpoint 3's reviewer flagged the single-cue version as
borderline; this is the fix.

The `spend` gap was brought into this grammar at checkpoint 4. Before that it
used bare `.hdr-dim` (app.js:926) and got italic and --ink-muted but no dashed
border, while the other two gaps did — so the rule as first written was not
true of all three. `.hdr-dim` now carries the dashed pill and the grammar
holds for every deliberate gap.

## Keyboard access to the Run tree

The Run tree is mouse-only. `renderTreeNode` (app/static/app.js:640-651)
emits `<div class="tree-node" data-node-id=...>` with no `tabindex`, and
`initRunTreeClicks` (app.js:862-868) registers a delegated `click` listener
and no `keydown`. Verified: `grep -c tabindex app/static/app.js` → 0,
`grep -c keydown app/static/app.js` → 0.

Selecting a node — the primary interaction on this screen — cannot be done
from the keyboard. `.tree-node:focus-visible` is styled and ready; making it
live needs `tabindex="0"`, a `keydown` handler for Enter and Space, and
probably `role="treeitem"`. That is an app.js change with its own checkpoint,
and it is not in batch 4's scope.

## Gap grammar — the closed list

Dashed edges have exactly five sanctioned uses, audited at checkpoint 5:

| Element | Selector | Means |
|---|---|---|
| Spend slot | `.hdr-dim` | no cost field in the stream |
| Vs-baseline significance | `.hdr-dim.panel-note` | nothing compares Band to baseline.published |
| No threshold available | `.dossier-no-threshold` | verdict carries no usable threshold |
| Not-hashed protocol tier | `.protocol-tier.not-hashed` | bounds this run only, not comparability |
| Orphan tree node | `.tree-node-orphan` | parent missing from the tree |

Ordinary empty states — `.panel-empty`, `.waiting`, `.stub` — are italic and
--ink-muted but NOT dashed. They mean "nothing here yet", which is different
from "deliberately withheld". Diluting dashed across both would cost the
honesty rule its only visual signal.

Tinted backgrounds have exactly three sanctioned uses: `.dossier-rule-trip`
(--crit-wash), `tr.metric-highlight` (--warn-wash), and `.worker-list
li.worker-stale` (--crit-wash, a stale worker on the Dashboard). Nothing else
in the app may take a tint. The rule trip's fill plus stripe is what keeps it
the loudest element on any screen; the stale worker never contests that,
because it renders on the Dashboard, which never shows a rule trip — the two
never compete for "loudest element".

Tint means persistent state, not transient feedback. A condition that stays
true until something changes it earns a fill. Feedback that fades on its own
— a click flash, a copy confirmation — gets border and colour only, never
fill.

Anything added later that is genuinely provisional should be dashed and added
to the table above. Anything that is persistent, harness-reported state
should be tinted and added to the list above. Anything else should not be.

**Checkpoint 5's audit findings are closed, not just recorded.** All three
were resolved at batch 5 checkpoint 1:

- `.worker-list li.worker-stale` — blessed as the third sanctioned tint,
  above. No CSS change; it was already correct.
- `.hash-value.copied` (index.html:738-741) — its `background: var(--pos-wash)`
  declaration is removed. It is an 800ms feedback flash (app.js:560-561), not
  a state, so it now reads `border-color: var(--pos); color: var(--pos);`
  instead of filling.
- `.chip-incumbent` (index.html:465-468) — its dead `background: var(--pos-wash)`
  declaration is deleted outright rather than fixed to actually render. `.chip`
  (index.html:697-698) declares `background: var(--sunken)` with equal
  specificity and was always winning the cascade on any element carrying both
  classes, so the wash never rendered. The decision is to keep the incumbent
  badge a neutral pill on purpose: it sits on the Run screen beside the rule
  trip, and a second tinted element there would cost the rule trip its status
  as the loudest thing on the screen. `color: var(--pos)` and `font-weight: 600`
  remain — the badge still reads as the incumbent, just without a fill.
