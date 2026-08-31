/** D1 journey.js tests — node --test, fixture only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { DICT } from "./copy.js";
import { buildJourney, journeyStripHtml, STAGES, buildReceipt } from "./journey.js";

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

function fold(events, start = initial()) {
  return events.reduce((s, ev) => reduce(s, ev), start);
}

function deepFreeze(value) {
  if (value === null || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  Object.freeze(value);
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return value;
}

function stageMap(journey) {
  return Object.fromEntries(journey.stages.map((s) => [s.id, s]));
}

describe("journey", () => {
  it("test_node3_journey_complete", () => {
    const state = fold(loadFixture());
    const j = buildJourney(state, 3);
    assert.ok(j);
    assert.equal(j.stages.length, 7);
    assert.equal(j.stages.filter((s) => s.status === "done").length, 7);
    assert.equal(j.decision, "accepted");
    assert.equal(j.loops, 0);
  });

  it("test_node4_retrying", () => {
    const state = fold(loadFixture());
    const j = buildJourney(state, 4);
    assert.ok(j);
    assert.equal(stageMap(j)["hidden-check"].status, "done");
    assert.equal(j.decision, "retrying");
    assert.equal(j.loops, 1);
  });

  it("test_node2_declined_at_quick_test", () => {
    const state = fold(loadFixture());
    const j = buildJourney(state, 2);
    assert.ok(j);
    const m = stageMap(j);
    assert.equal(m["quick-test"].status, "failed");
    assert.equal(m["repeat-test"].status, "skipped");
    assert.equal(m["hidden-check"].status, "skipped");
    assert.notEqual(m["repeat-test"].status, "failed");
    assert.notEqual(m["hidden-check"].status, "failed");
    assert.equal(j.decision, "declined");
  });

  it("test_node1_loops_counted", () => {
    // Derivation: one inconclusive verdict for node 1 in fake-events.jsonl.
    const events = loadFixture();
    const loops = events.filter(
      (e) =>
        e.type === "verdict" &&
        e.node === 1 &&
        e.state === "inconclusive",
    ).length;
    assert.equal(loops, 1);
    const j = buildJourney(fold(events), 1);
    assert.ok(j);
    assert.equal(j.loops, 1);
  });

  it("test_unknown_node_null", () => {
    const state = fold(loadFixture());
    assert.equal(buildJourney(state, 99), null);
    assert.equal(buildJourney(state, "missing"), null);
    assert.equal(buildJourney(null, 1), null);
  });

  it("test_pure", () => {
    const state = deepFreeze(fold(loadFixture()));
    const a = buildJourney(state, 3);
    const b = buildJourney(state, 3);
    assert.deepEqual(a, b);
    assert.equal(STAGES.length, 7);
  });

  it("test_dossier_contains_journey_strip", () => {
    const state = fold(loadFixture());
    const html = journeyStripHtml(buildJourney(state, 3));
    const stages = [...html.matchAll(/class="stage stage--(\w+)"/g)].map(
      (m) => m[1],
    );
    assert.equal(stages.length, 7);
    assert.ok(stages.every((s) => s === "done"));
    assert.match(html, /class="journey-strip"/);
  });

  it("test_zero_spend_on_level1_stop", () => {
    const state = {
      ...initial(),
      cascade: {
        ...initial().cascade,
        byNode: {
          5: [{ level: "omega", passed: false, trips: ["C1"], llm_calls: 0, runs: 0 }],
        },
      },
      reliability: {
        ...initial().reliability,
        ruleTrips: [
          { node: 5, rule_id: "C1", statement: "Never reads validation labels." },
        ],
      },
    };
    const receipt = buildReceipt(state, { available: true, rules: [] }, 5);
    assert.equal(receipt.spend.readings, 0);
    assert.equal(receipt.spend.runs, 0);
    assert.equal(receipt.stoppedAt, "free");
    const html = journeyStripHtml(
      { stages: STAGES.map((s) => ({ ...s, status: "failed" })), loops: 0 },
      receipt,
    );
    assert.ok(html.includes(DICT.receiptStopFree.word));
  });

  it("test_tripped_rule_quoted", () => {
    const state = fold(loadFixture());
    const receipt = buildReceipt(state, null, 2);
    assert.ok(receipt.levels.some((lv) =>
      lv.tripped.some((t) => t.statement.includes("self-label")),
    ));
  });

  it("test_semantic_line_counts_contract", () => {
    const state = fold(loadFixture());
    const contract = {
      available: true,
      rules: [
        { check: "static" },
        { check: "llm" },
        { check: "llm" },
      ],
    };
    const receipt = buildReceipt(state, contract, 1);
    assert.equal(receipt.semanticLine, DICT.receiptSemantic.word.replace("{n}", "2"));
  });

  it("test_full_pass_receipt", () => {
    const state = fold(loadFixture());
    const receipt = buildReceipt(state, { available: true, rules: [] }, 1);
    assert.ok(receipt);
    assert.equal(receipt.stoppedAt, null);
    assert.equal(receipt.levels[0].passed, true);
  });

  it("test_no_cascade_null", () => {
    assert.equal(buildReceipt(initial(), null, 99), null);
  });
});
