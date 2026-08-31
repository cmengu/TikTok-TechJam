/** D3 tree enrichment tests — node --test, golden fixture. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { buildTree, moveTargets } from "./tree.js";

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
  return readFileSync(FIXTURE, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

function byId(roots) {
  const map = new Map();
  function walk(entries) {
    for (const e of entries) {
      map.set(String(e.node.id), e);
      walk(e.children);
    }
  }
  walk(roots);
  return map;
}

describe("tree — D3 enrichment", () => {
  it("test_accepted_path_marked", () => {
    const state = fold(loadFixture());
    const map = byId(buildTree(state));
    assert.equal(map.get("3").onBestPath, true);
    assert.equal(map.get("3").plainState.word, "accepted");
    // Incumbent 3's parent chain includes 1.
    assert.equal(map.get("1").onBestPath, true);
  });

  it("test_declined_dimmed", () => {
    const state = fold(loadFixture());
    const map = byId(buildTree(state));
    assert.equal(map.get("2").dimmed, true);
    assert.equal(map.get("3").dimmed, false);
  });

  it("test_edge_labels_from_moves", () => {
    const state = fold(loadFixture());
    const map = byId(buildTree(state));
    // Three moves, each immediately preceding nodes 1, 2, 3; node 4 has none.
    assert.equal(map.get("1").edgeLabel, "new idea");
    assert.equal(map.get("2").edgeLabel, "new idea");
    assert.equal(map.get("3").edgeLabel, "new idea");
    assert.equal(map.get("4").edgeLabel, null);
  });

  it("test_loop_badge", () => {
    const state = fold(loadFixture());
    const map = byId(buildTree(state));
    assert.equal(map.get("1").loops, 1);
    assert.equal(map.get("4").loops, 1);
    assert.equal(map.get("3").loops, 0);
  });

  it("test_no_incumbent_no_crash", () => {
    const state = fold(loadFixture());
    state.incumbent = null;
    assert.doesNotThrow(() => buildTree(state));
    const map = byId(buildTree(state));
    assert.equal(map.get("3").onBestPath, false);
    assert.equal(map.get("1").onBestPath, false);
  });

  it("moveTargets pairs moves to produced attempts", () => {
    const state = fold(loadFixture());
    const targets = moveTargets(state);
    assert.equal(targets.length, 3);
    assert.deepEqual(
      targets.map((t) => t.nodeId),
      [1, 2, 3],
    );
  });
});
