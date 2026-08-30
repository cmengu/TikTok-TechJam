/** Checkpoint C reducer tests — node --test, fixture only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce, EVENT_TYPES, STATES } from "./reducer.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "fake-events.jsonl",
);
const HEARTBEAT_FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "fake-heartbeats.jsonl",
);
const TYPES_PY = join(__dirname, "..", "..", "harness", "types.py");
// Hand-written to the event contract: one valid line per Phase 2 event plus
// one malformed line per type. Used until the golden fixture carries them all.
const PHASE2_FIXTURE = join(__dirname, "fixtures", "phase2-events.jsonl");

function loadJsonl(path) {
  const text = readFileSync(path, "utf8");
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function loadFixture() {
  return loadJsonl(FIXTURE);
}

function loadHeartbeats() {
  return loadJsonl(HEARTBEAT_FIXTURE);
}

function countByType(events, types) {
  const counts = Object.fromEntries(types.map((t) => [t, 0]));
  for (const ev of events) {
    if (ev.type in counts) counts[ev.type] += 1;
  }
  return counts;
}

function logCounts(label, counts) {
  console.log(label);
  for (const [type, n] of Object.entries(counts)) {
    console.log(`  ${type}: ${n}`);
  }
}

function fold(events, start = initial()) {
  return events.reduce((s, ev) => reduce(s, ev), start);
}

function deepEqual(a, b) {
  assert.deepEqual(a, b);
}

// Weaves two seq-ordered streams together, preserving each stream's own
// internal order, spaced out proportionally to length rather than
// concatenated. Concatenating (all of a, then all of b) would let any bug in
// a per-stream duplicate/seq guard hide behind the fact that the tail of a
// concatenated corpus always has the highest seq of its own stream — see
// Handoff_app.md, test_heartbeat_does_not_touch_lastSeq.
function interleave(a, b) {
  const merged = [];
  let ai = 0;
  let bi = 0;
  while (ai < a.length || bi < b.length) {
    const aFrac = a.length ? ai / a.length : Infinity;
    const bFrac = b.length ? bi / b.length : Infinity;
    if (bFrac < aFrac) {
      merged.push(b[bi++]);
    } else if (ai < a.length) {
      merged.push(a[ai++]);
    } else {
      merged.push(b[bi++]);
    }
  }
  return merged;
}

function corpus() {
  return interleave(loadFixture(), loadHeartbeats());
}

function deepFreeze(value) {
  if (value === null || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  Object.freeze(value);
  for (const key of Object.keys(value)) {
    deepFreeze(value[key]);
  }
  return value;
}

// Per the state contract's feed rule: "measurement", "heartbeat",
// "research_source", "cache_lookup" are excluded; everything else (including
// hypothesis_queued, confirmed feed-worthy — see Handoff_app.md) is included.
const FEED_EXCLUDED_TYPES = new Set([
  "measurement",
  "heartbeat",
  "research_source",
  "cache_lookup",
]);

describe("reducer — baseline (Checkpoint A/B)", () => {
  it("node count equals node_created count over the fake stream", () => {
    const events = loadFixture();
    const created = events.filter((e) => e.type === "node_created").length;
    const state = fold(events);
    assert.equal(Object.keys(state.nodes).length, created);
  });

  it("deterministic — reducing the same stream twice gives deep-equal states", () => {
    const events = loadFixture();
    deepEqual(fold(events), fold(events));
  });

  it("reconnect equivalence — reduce(all) deep-equals reduce(first 100) then reduce(rest)", () => {
    const events = loadFixture();
    const all = fold(events);
    const mid = fold(events.slice(0, 100));
    const resumed = fold(events.slice(100), mid);
    deepEqual(all, resumed);
  });

  it("latest heartbeat only — after 5 heartbeats from worker w1, workers.w1 is the last one", () => {
    let state = initial();
    let last = null;
    for (let i = 0; i < 5; i++) {
      last = {
        type: "heartbeat",
        seq: i + 1,
        worker: "w1",
        status: i === 4 ? "idle" : "busy",
        progress: i,
      };
      state = reduce(state, last);
    }
    assert.equal(state.workers.w1, last);
    assert.equal(state.workers.w1.status, "idle");
  });

  it("no mutation — the input state object is unchanged after reduce", () => {
    const state = initial();
    const snapshot = structuredClone(state);
    reduce(state, {
      type: "node_created",
      seq: 1,
      id: 1,
      parent: null,
      kind: "draft",
    });
    deepEqual(state, snapshot);
  });

  it("the two fixtures together exercise every EVENT_TYPES member (Checkpoint B: two files, never regenerated to patch a gap)", () => {
    const nonHeartbeatTypes = EVENT_TYPES.filter((t) => t !== "heartbeat");

    const eventCounts = countByType(loadFixture(), nonHeartbeatTypes);
    logCounts("per-type counts in tests/fixtures/fake-events.jsonl:", eventCounts);
    const missingFromEvents = nonHeartbeatTypes.filter((t) => eventCounts[t] === 0);
    assert.deepEqual(
      missingFromEvents,
      [],
      `fake-events.jsonl is missing event type(s): ${missingFromEvents.join(", ")}`,
    );

    const heartbeatCounts = countByType(loadHeartbeats(), ["heartbeat"]);
    logCounts("per-type counts in tests/fixtures/fake-heartbeats.jsonl:", heartbeatCounts);
    assert.ok(
      heartbeatCounts.heartbeat > 0,
      "fake-heartbeats.jsonl has no heartbeat events",
    );
  });
});

describe("reducer — Checkpoint C: state contract", () => {
  it("test_all_event_types_reduce_without_throwing", () => {
    const state = fold(corpus());
    deepEqual(state.unknown, {});
    assert.equal(state.nodeOrder.length, 3);
  });

  it("test_reduce_is_pure", () => {
    let state = initial();
    for (const ev of corpus()) {
      deepFreeze(state);
      state = reduce(state, ev); // throws if reduce ever wrote through a frozen ref
    }
    assert.equal(state.nodeOrder.length, 3);
    assert.equal(state.run.status, "ended");
  });

  it("test_protocol_object_retained_whole", () => {
    const events = loadFixture();
    const runStarted = events.find((e) => e.type === "run_started");
    const state = fold(events);
    deepEqual(state.run.protocol, runStarted.protocol);
  });

  it("test_node_keeps_hypothesis_id", () => {
    const state = fold(loadFixture());
    assert.equal(state.nodes[1].hypothesisId, "h-feat-1");
    assert.equal(state.nodes[2].hypothesisId, "h-feat-2");
    assert.equal(state.nodes[3].hypothesisId, "h-train-1");
  });

  it("test_verdict_band_retained_per_metric", () => {
    const state = fold(loadFixture());
    deepEqual(state.nodes[1].bands.cvr_auc, [0.5, 0.52]);
    deepEqual(state.nodes[3].bands.cvr_auc, [0.52, 0.54]);
  });

  it("test_scores_and_seeds_stay_parallel", () => {
    const state = fold(loadFixture());
    const node3 = state.nodes[3];
    assert.equal(node3.scores.cvr_auc.length, node3.seeds.length);
    // The fixture's node 3 emits a replicating verdict (seed 1) and then a
    // promoted one over three seeds; the reducer concatenates both, so seed 1
    // legitimately appears twice.
    deepEqual(node3.scores.cvr_auc, [0.531, 0.529, 0.53, 0.528]);
    deepEqual(node3.seeds, [1, 1, 2, 3]);
  });

  it("test_failure_and_recovery_counted_by_class", () => {
    const state = fold(loadFixture());
    deepEqual(state.reliability.failuresByClass, { cuda_oom: 1, stall: 1 });
    deepEqual(state.reliability.recoveriesByClass, { cuda_oom: 1, stall: 1 });
    assert.equal(state.nodes[2].failures.length, 2);
    assert.equal(state.nodes[2].recoveries.length, 2);
  });

  it("test_rule_trip_counted_by_rule", () => {
    const state = fold(loadFixture());
    // Two shapes coexist in the fixture: the pre-Phase-2 leak-audit trip keyed
    // on `rule`, and the step-7 cascade trip keyed on `rule_id`.
    deepEqual(state.reliability.ruleTripsByRule, { no_test_peek: 1, C7: 1 });
    assert.equal(state.nodes[2].ruleTrips.length, 2);
  });

  it("test_research_sources_deduped_by_id", () => {
    let state = initial();
    state = reduce(state, {
      type: "research_source",
      seq: 1,
      id: "src-1",
      title: "First title",
      summary: "x",
    });
    state = reduce(state, {
      type: "research_source",
      seq: 2,
      id: "src-2",
      title: "Other",
      summary: "x",
    });
    state = reduce(state, {
      type: "research_source",
      seq: 3,
      id: "src-1",
      title: "Updated title",
      summary: "x",
    });
    assert.equal(state.research.sources.length, 2);
    const src1 = state.research.sources.find((s) => s.id === "src-1");
    assert.equal(src1.title, "Updated title");
  });

  it("test_cache_lookup_tallies", () => {
    const state = fold(loadFixture());
    assert.equal(state.research.hits, 1);
    assert.equal(state.research.misses, 1);
    assert.equal(state.research.confirmed, 1);
    assert.equal(state.research.contradicted, 0);
  });

  it("test_submission_and_intervention_recorded", () => {
    const state = fold(loadFixture());
    assert.equal(state.submissions.length, 1);
    assert.equal(state.submissions[0].path, "submission/pred.csv");
    assert.equal(state.interventions.length, 1);
    assert.equal(state.interventions[0].kind, "pause_queue");
  });

  it("test_incumbent_changed_sets_current_and_appends_history", () => {
    const events = loadFixture();
    const incumbentChanged = events.find((e) => e.type === "incumbent_changed");
    const state = fold(events);
    assert.equal(state.incumbent, incumbentChanged.node);
    assert.equal(state.incumbentChanges.length, 1);
  });

  it("test_prediction_is_stored_with_its_proven_fields", () => {
    const events = loadFixture();
    const predictionEv = events.find((e) => e.type === "prediction");
    const state = fold(events);
    assert.equal(state.predictions.length, 1);
    assert.equal(state.predictions[0].node, predictionEv.node);
    assert.equal(state.predictions[0].metric, predictionEv.metric);
    assert.equal(state.predictions[0].value, predictionEv.value);
    assert.equal(state.predictions[0].summary, predictionEv.summary);
    // harness/measure.py:512-513 also emit best_reported and band:
    //   best_reported=next_best,
    //   band=_band_payload(self.band) if self.band else None,
    // but the committed fixture's prediction event (tests/fixtures/fake-events.jsonl
    // seq 115) carries neither key — only node, metric, value, summary.
    assert.ok(
      !("best_reported" in predictionEv),
      "fake_run.py's prediction event omits this; if this fails, fake_run.py has been fixed and this assertion should be inverted",
    );
    assert.ok(
      !("band" in predictionEv),
      "fake_run.py's prediction event omits this; if this fails, fake_run.py has been fixed and this assertion should be inverted",
    );
  });

  it("test_run_lifecycle_status", () => {
    assert.equal(initial().run.status, "waiting");
    const events = loadFixture();
    assert.equal(fold(events.slice(0, 1)).run.status, "running");
    const final = fold(events);
    assert.equal(final.run.status, "ended");
    assert.equal(final.run.endReason, "budget_demo");
  });

  it("test_feed_excludes_measurement_ticks", () => {
    const events = loadFixture();
    const state = fold(events);
    assert.ok(state.feed.every((e) => !FEED_EXCLUDED_TYPES.has(e.type)));
    const expected = events.filter((e) => !FEED_EXCLUDED_TYPES.has(e.type)).length;
    assert.equal(state.feed.length, expected);
  });

  it("test_unknown_event_type_is_counted_not_thrown", () => {
    let state = initial();
    const unknownTypeEvent = { type: "future_event", seq: 1, summary: "x" };
    state = reduce(state, unknownTypeEvent);
    assert.equal(state.unknown.future_event, 1);
    assert.equal(state.log.length, 1);
    assert.equal(state.log[0], unknownTypeEvent);

    const unknownStateEvent = {
      type: "state_changed",
      seq: 2,
      node: 999,
      state: "bogus",
      summary: "x",
    };
    state = reduce(state, unknownStateEvent);
    assert.equal(state.unknown["state:bogus"], 1);
  });

  it("test_replay_is_idempotent — duplicate tolerance, not tautological same-input-twice", () => {
    const events = corpus();
    const first = fold(events);
    const replayed = fold(events, first); // resend the same stream into an already-warm state
    deepEqual(replayed, first);
  });

  it("test_event_vocabulary_matches_python", () => {
    const src = readFileSync(TYPES_PY, "utf8");
    // Strip Python "# ..." comments before matching: a trailing comment can
    // itself contain a parenthesized aside (e.g. harness/types.py:40's
    // "# Phase 5 (Plan_delta §1: ...)"), whose ")" would otherwise close the
    // regex's capture group early and pull comment text in as fake entries.
    const srcNoComments = src
      .split("\n")
      .map((line) => line.replace(/#.*$/, ""))
      .join("\n");
    const extractTuple = (name) => {
      const m = srcNoComments.match(new RegExp(`${name}\\s*=\\s*\\(([^)]*)\\)`));
      assert.ok(m, `could not find ${name} in harness/types.py`);
      return m[1]
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => s.replace(/^["']|["']$/g, ""));
    };
    deepEqual(extractTuple("EVENT_TYPES"), EVENT_TYPES);
    deepEqual(extractTuple("STATES"), STATES);
  });
});

describe("reducer — Checkpoint C: queue", () => {
  const queueEvents = [
    { type: "hypothesis_queued", seq: 1, id: "a", stage: "data", mechanism: "m1", parent_node: null, summary: "x" },
    { type: "hypothesis_queued", seq: 2, id: "b", stage: "data", mechanism: "m2", parent_node: null, summary: "x" },
    { type: "hypothesis_queued", seq: 3, id: "c", stage: "data", mechanism: "m3", parent_node: null, summary: "x" },
    { type: "queue_reordered", seq: 4, order: ["b"], summary: "x" },
  ];

  it("test_queue_reorder_preserves_unnamed_entries", () => {
    const state = fold(queueEvents);
    deepEqual(state.queue.map((q) => q.id), ["b", "a", "c"]);
  });

  it("test_queue_movement_tracked", () => {
    const state = fold(queueEvents);
    const byId = Object.fromEntries(state.queue.map((q) => [q.id, q]));
    assert.equal(byId.b.position, 0);
    assert.equal(byId.b.prevPosition, 1);
    assert.equal(byId.b.movement, 1); // moved up one slot

    assert.equal(byId.a.position, 1);
    assert.equal(byId.a.prevPosition, 0);
    assert.equal(byId.a.movement, -1); // displaced down one slot

    assert.equal(byId.c.position, 2);
    assert.equal(byId.c.prevPosition, 2);
    assert.equal(byId.c.movement, 0); // unnamed and already last, unchanged
  });

  it("test_queue_entry_links_to_node", () => {
    const withNode = [
      ...queueEvents,
      { type: "node_created", seq: 5, id: 1, parent: null, kind: "draft", hypothesis_id: "a", summary: "x" },
    ];
    const state = fold(withNode);
    const byId = Object.fromEntries(state.queue.map((q) => [q.id, q]));
    assert.equal(byId.a.nodeId, 1);
    assert.equal(byId.a.started, true);
    assert.equal(byId.b.nodeId, null);
    assert.equal(byId.b.started, false);
    assert.equal(byId.c.nodeId, null);
    assert.equal(byId.c.started, false);
  });
});

describe("reducer — Checkpoint C: heartbeat isolation", () => {
  it("test_heartbeat_does_not_touch_lastSeq", () => {
    let state = initial();
    for (const ev of corpus()) {
      const before = state.lastSeq;
      state = reduce(state, ev);
      if (ev.type === "heartbeat") {
        assert.equal(state.lastSeq, before);
      } else {
        assert.equal(state.lastSeq, ev.seq);
      }
    }
  });

  it("test_heartbeat_excluded_from_log_and_feed", () => {
    const state = fold(corpus());
    assert.ok(state.log.every((e) => e.type !== "heartbeat"));
    assert.ok(state.feed.every((e) => e.type !== "heartbeat"));
    assert.equal(state.log.length, loadFixture().length);
  });
});

describe("reducer — Phase 2 (F1: vocabulary and slices)", () => {
  const loadPhase2 = () => loadJsonl(PHASE2_FIXTURE);
  const foldPhase2 = () => loadPhase2().reduce(reduce, initial());

  it("test_phase2_fixture_reduces_with_no_unknown_types", () => {
    const state = foldPhase2();
    const unknownTypes = Object.keys(state.unknown).filter(
      (k) => !k.startsWith("malformed:"),
    );
    deepEqual(unknownTypes, []);
  });

  it("test_move_selected_collected_in_order", () => {
    const moves = foldPhase2().moves;
    deepEqual(
      moves.map((m) => [m.round, m.kind]),
      [
        [0, "draft"],
        [1, "debug"],
        [2, null],
      ],
    );
    // A null kind is the at-cap move, not a malformed one.
    assert.equal(moves[2].reason, "at branch cap");
  });

  it("test_cascade_history_is_per_node", () => {
    const cascade = foldPhase2().cascade;
    deepEqual(
      cascade.byNode[1].map((e) => e.level),
      ["omega", "v_sem", "smoke"],
    );
    deepEqual(
      cascade.byNode[2].map((e) => e.level),
      ["omega"],
    );
  });

  it("test_cascade_counts_where_nodes_died_and_what_it_spent", () => {
    const cascade = foldPhase2().cascade;
    // Node 2 died at omega — before any LLM call or run. That is the
    // "rejected for free" number the dashboard puts on screen.
    deepEqual(cascade.rejected, { omega: 1, v_sem: 0, smoke: 0 });
    deepEqual(cascade.counters, { llmCalls: 1, runs: 1 });
  });

  it("test_lessons_collected", () => {
    const lessons = foldPhase2().lessons;
    assert.equal(lessons.length, 1);
    assert.equal(lessons[0].family, "features/target-encoding");
    assert.equal(lessons[0].verdict, "inconclusive");
  });

  it("test_forbidden_keeps_the_first_sighting", () => {
    const forbidden = foldPhase2().forbidden;
    deepEqual(Object.keys(forbidden), ["crossed-ids"]);
    // Seen again in round 3, but first_round and the original round stand.
    assert.equal(forbidden["crossed-ids"].round, 2);
    assert.equal(forbidden["crossed-ids"].first_round, 1);
  });

  it("test_attribution_keyed_by_node", () => {
    const attribution = foldPhase2().attribution;
    assert.equal(attribution.byNode[1].result, "unclear");
    assert.equal(attribution.byNode[1].observables[0].moved, false);
  });

  it("test_submission_run_collected", () => {
    const runs = foldPhase2().submissionRuns;
    assert.equal(runs.length, 1);
    assert.equal(runs[0].commit, "8ce003e");
    assert.equal(runs[0].env.SEED, "1");
  });

  it("test_rule_trip_keyed_on_rule_id", () => {
    const state = foldPhase2();
    deepEqual(state.reliability.ruleTripsByRule, { C1: 1 });
  });

  it("test_malformed_lines_are_skipped_not_thrown", () => {
    const state = foldPhase2();
    // One malformed line per type, each counted and each leaving its slice alone.
    deepEqual(state.unknown, {
      "malformed:move_selected": 1,
      "malformed:verify_level": 1,
      "malformed:lesson_written": 1,
      "malformed:proposal_rejected": 1,
      "malformed:attribution_checked": 1,
      "malformed:submission_run": 1,
    });
    assert.equal(state.moves.length, 3);
    assert.equal(state.lessons.length, 1);
    assert.equal(state.submissionRuns.length, 1);
    assert.equal(Object.keys(state.attribution.byNode).length, 1);
    assert.equal(Object.keys(state.forbidden).length, 1);
  });

  it("test_reduce_stays_pure_over_the_phase2_fixture", () => {
    let state = initial();
    for (const ev of loadPhase2()) {
      deepFreeze(state);
      state = reduce(state, ev);
    }
    assert.equal(state.run.status, "ended");
  });

  it("test_old_fixture_still_reduces_identically_in_the_untouched_slices", () => {
    // The orders' F1 gate: adding Phase 2 types must not move the old state.
    const state = fold(loadFixture());
    assert.equal(state.nodeOrder.length, 3);
    assert.equal(state.run.status, "ended");
    deepEqual(Object.keys(state.unknown), []);
  });
});
