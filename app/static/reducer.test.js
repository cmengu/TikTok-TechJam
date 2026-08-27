/** Phase 2 reducer tests — node --test, fixture only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "fake-events.jsonl",
);

function loadFixture() {
  const text = readFileSync(FIXTURE, "utf8");
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
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
});
