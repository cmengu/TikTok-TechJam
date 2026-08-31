/** E6 Ideas view-model tests — node --test, fixture only (no DOM). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { buildIdeas } from "./ideas.js";
import { fmtDelta } from "./copy.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");
const APP = join(__dirname, "app.js");

function loadJsonl(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

describe("ideas", () => {
  it("test_three_shelves_partition", () => {
    const vm = buildIdeas(fold(loadJsonl(FIXTURE)));
    assert.ok(vm);
    const ids = [...vm.inPlay, ...vm.done, ...vm.banned].map((c) => c.id);
    assert.equal(ids.length, 6);
    assert.equal(new Set(ids).size, 6);
    assert.deepEqual(
      vm.banned.map((c) => c.id).sort(),
      ["h-feat-2"],
    );
    assert.ok(vm.done.find((c) => c.id === "h-train-1"));
    assert.ok(vm.inPlay.find((c) => c.id === "h-train-2"));
    assert.ok(vm.inPlay.find((c) => c.id === "h-obj-2"));
  });

  it("test_honesty_column", () => {
    const vm = buildIdeas(fold(loadJsonl(FIXTURE)));
    const train = vm.done.find((c) => c.id === "h-train-1");
    assert.ok(train);
    // expected_gain is absent from the fixture's queued events.
    assert.equal(train.expectedGain, null);
    assert.equal(train.actualDelta, 0.031);
    assert.equal(fmtDelta(train.actualDelta), "+0.0310");
  });

  it("test_banned_carries_reason", () => {
    const vm = buildIdeas(fold(loadJsonl(FIXTURE)));
    assert.equal(vm.banned.length, 1);
    assert.equal(vm.banned[0].pattern, "crossed-ids");
    assert.equal(vm.banned[0].reason, "forbidden");
    assert.match(String(vm.banned[0].note), /crossed-ids/);
  });

  it("test_empty_state", () => {
    assert.equal(buildIdeas(null), null);
    assert.equal(buildIdeas({}), null);
    const empty = buildIdeas(initial());
    assert.deepEqual(empty, { inPlay: [], done: [], banned: [] });
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Hypotheses")'), false);
    assert.match(src, /hash:\s*"hypotheses"/);
    assert.match(src, /render:\s*renderIdeas/);
  });
});
