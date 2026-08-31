/** V6 wall.js tests — node --test, no DOM. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DICT } from "./copy.js";
import { buildWall, wallHtml } from "./wall.js";

function payload(overrides = {}) {
  return {
    available: true,
    holdout_visits: 1,
    holdout_cap: 12,
    ladder_queries: 3,
    digests_ok: true,
    ...overrides,
  };
}

function deepFreeze(value) {
  if (value && typeof value === "object") {
    Object.freeze(value);
    for (const k of Object.keys(value)) deepFreeze(value[k]);
  }
  return value;
}

describe("wall", () => {
  it("test_meter_visits_of_cap", () => {
    const wall = buildWall(payload({ holdout_visits: 3, holdout_cap: 12 }));
    assert.equal(wall.visits, 3);
    assert.equal(wall.cap, 12);
    assert.equal(wall.pct, 25);
    const html = wallHtml(wall);
    assert.match(html, /visited 3 of 12/);
  });

  it("test_queries_echoed_not_computed", () => {
    const wall = buildWall(payload({ ladder_queries: 7, holdout_visits: 2 }));
    assert.equal(wall.queries, 7);
    assert.notEqual(wall.queries, wall.visits);
  });

  it("test_missing_payload_degrades", () => {
    assert.deepEqual(buildWall(null), { available: false });
    assert.deepEqual(buildWall({ available: false }), { available: false });
    assert.deepEqual(buildWall({ available: true }), { available: false });
    assert.equal(wallHtml({ available: false }), "");
  });

  it("test_zero_holdout_renders", () => {
    const wall = buildWall(payload({ holdout_visits: 0, digests_ok: null }));
    assert.equal(wall.visits, 0);
    assert.equal(wall.digestsOk, false);
    const html = wallHtml(wall);
    assert.match(html, /visited 0 of 12/);
    assert.equal(html.includes(DICT.wallDigests.word), false);
  });

  it("test_pure", () => {
    const p = deepFreeze(payload());
    assert.deepEqual(buildWall(p), buildWall(p));
  });

  it("test_caption_is_dictionary", () => {
    const wall = buildWall(payload());
    assert.equal(wall.caption, DICT.wallCaption.word);
    assert.ok(wallHtml(wall).includes(DICT.wallCaption.word));
  });
});
