/** Phase 2 reducer tests — node --test, fixture only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";

// Mirrors harness/types.py EVENT_TYPES. No Python at run time here (see file
// header), so this list is copied by hand — keep it in sync if that tuple
// changes.
const EVENT_TYPES = [
  "run_started",
  "node_created",
  "state_changed",
  "heartbeat",
  "measurement",
  "verdict",
  "failure",
  "recovery",
  "rule_trip",
  "research_source",
  "cache_lookup",
  "hypothesis_queued",
  "queue_reordered",
  "submission_written",
  "intervention",
  "run_ended",
];

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

describe("reducer", () => {
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
    // heartbeat lands in the sidecar heartbeat.jsonl by design (EventLog.heartbeat,
    // not .emit) — fake-events.jsonl can never carry it. See
    // context/Handoff_app.md, Tests section, "Heartbeats need a SECOND fixture".
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
