/** V3 memory.js tests — node --test, fixture only. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { DICT } from "./copy.js";
import { buildMemory, memoryPageHtml, bannedRows } from "./memory.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");
const FIXTURE = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");

function fold(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line))
    .reduce((s, ev) => reduce(s, ev), initial());
}

function deepFreeze(value) {
  if (value && typeof value === "object") {
    Object.freeze(value);
    for (const k of Object.keys(value)) deepFreeze(value[k]);
  }
  return value;
}

describe("memory", () => {
  it("test_three_sections_fixed_order", () => {
    const html = memoryPageHtml(
      buildMemory(initial(), {
        available: true,
        weak: ["features/x"],
        directions: ["y (no prior)"],
        forbidden: ["z"],
        text: "weak components\n- features/x\ndirections\n- y (no prior)\nforbidden\n- z",
      }),
    );
    const weakAt = html.indexOf(DICT.memoryWeak.word);
    const dirAt = html.indexOf(DICT.memoryDirections.word);
    const banAt = html.indexOf(DICT.memoryBanned.word);
    assert.ok(weakAt >= 0 && dirAt > weakAt && banAt > dirAt);
  });

  it("test_banned_joins_lesson_fields", () => {
    const state = fold(FIXTURE);
    const rows = bannedRows(state);
    assert.ok(rows.length >= 1);
    const crossed = rows.find((r) => r.pattern === "crossed-ids");
    assert.ok(crossed);
    assert.equal(crossed.defect, "no_gain");
    assert.equal(crossed.node, 2);
    assert.equal(crossed.round, 1);
    assert.equal(crossed.seeded, false);
  });

  it("test_round0_labelled_seeded", () => {
    const state = {
      ...initial(),
      forbidden: { "seed-pattern": { pattern: "seed-pattern", round: 0 } },
      lessons: [
        { pattern: "seed-pattern", defect: "crash", round: 0, node: 0 },
      ],
    };
    const vm = buildMemory(state, {
      available: true,
      weak: [],
      directions: [],
      forbidden: ["seed-pattern"],
      text: "x",
    });
    assert.equal(vm.banned[0].seeded, true);
    assert.ok(memoryPageHtml(vm).includes(DICT.memorySeeded.word));
  });

  it("test_verbatim_is_payload_not_recomputed", () => {
    const text = "weak components\n- (none)\ndirections\n- no prior\nforbidden\n- (none)";
    const vm = buildMemory(initial(), {
      available: true,
      weak: [],
      directions: ["no prior"],
      forbidden: [],
      text,
    });
    assert.equal(vm.verbatim, text);
    assert.ok(memoryPageHtml(vm).includes(text));
  });

  it("test_empty_memory_teaches", () => {
    const vm = buildMemory(initial(), {
      available: false,
      reason: DICT.memoryEmpty.word,
    });
    assert.equal(vm.empty, true);
    const html = memoryPageHtml(vm);
    assert.ok(html.includes(DICT.memoryEmpty.word));
    assert.equal(html.includes("<pre>"), false);
  });

  it("test_pure", () => {
    const state = deepFreeze(fold(FIXTURE));
    const payload = deepFreeze({
      available: true,
      weak: ["a"],
      directions: ["b"],
      forbidden: [],
      text: "t",
    });
    assert.deepEqual(buildMemory(state, payload), buildMemory(state, payload));
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.match(src, /hash:\s*"learned"/);
    assert.match(src, /render:\s*renderMemory/);
  });
});
