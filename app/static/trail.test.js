/** D4 move trail tests — node --test, golden fixture. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { buildMoveTrail } from "./feed.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "fake-events.jsonl",
);

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

function loadFixture() {
  return readFileSync(FIXTURE, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

describe("trail", () => {
  it("test_trail_orders_and_links", () => {
    const trail = buildMoveTrail(fold(loadFixture()));
    assert.equal(trail.length, 3);
    assert.deepEqual(
      trail.map((row) => row.href),
      ["#/run/1", "#/run/2", "#/run/3"],
    );
    for (const row of trail) {
      assert.match(row.text, /Next move:/);
    }
  });

  it("test_trail_never_links_null", () => {
    const state = fold(loadFixture());
    // A trailing move with no following node_created.
    state.moves = [
      ...state.moves,
      {
        type: "move_selected",
        seq: 999,
        round: 9,
        kind: "draft",
        parent: null,
        reason: "no build",
      },
    ];
    const trail = buildMoveTrail(state);
    assert.equal(trail.length, 4);
    assert.equal(trail[3].href, null);
    assert.match(trail[3].text, /Next move:/);
    for (const row of trail) {
      assert.equal(String(row.href || "").includes("null"), false);
      assert.notEqual(row.href, "#/run/null");
    }
  });
});
