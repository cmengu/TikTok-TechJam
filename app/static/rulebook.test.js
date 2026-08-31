/** V1 rulebook.js tests — node --test, fixture only (no DOM, no fetch). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { DICT } from "./copy.js";
import { buildRulebook, rulebookPageHtml } from "./rulebook.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");
const RULES = join(__dirname, "fixtures", "rules.jsonl");
const EVENTS = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");

function loadRules() {
  return readFileSync(RULES, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

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

const PAYLOAD = { available: true, rules: loadRules() };

describe("rulebook", () => {
  it("test_nine_cards_from_contract", () => {
    // Name kept from the addendum. candidate/rules.jsonl has 18 rows, not 9 —
    // the file is right; the card count follows the fixture.
    const vm = buildRulebook(PAYLOAD, initial());
    assert.equal(vm.available, true);
    assert.equal(vm.cards.length, PAYLOAD.rules.length);
    assert.equal(vm.cards.length, 18);
    assert.equal(vm.cards[0].statement, PAYLOAD.rules[0].statement);
    assert.equal(vm.cards[0].id, "C1");
  });

  it("test_check_labels_plain", () => {
    const vm = buildRulebook(PAYLOAD, initial());
    const blob = JSON.stringify(vm);
    for (const term of ["omega", "v_sem", "llm"]) {
      assert.equal(
        new RegExp(`\\b${term}\\b`, "i").test(blob),
        false,
        `jargon "${term}" leaked into the fold`,
      );
    }
    const staticCard = vm.cards.find((c) => c.id === "C1");
    const llmCard = vm.cards.find((c) => c.id === "C2");
    assert.equal(staticCard.checkLabel, DICT.checkStatic.word);
    assert.equal(llmCard.checkLabel, DICT.checkLlm.word);
  });

  it("test_trip_counts_join", () => {
    const state = fold(EVENTS);
    const vm = buildRulebook(PAYLOAD, state);
    for (const card of vm.cards) {
      const expected = state.reliability.ruleTripsByRule[card.id] || 0;
      assert.equal(card.trips, expected, `trips for ${card.id}`);
    }
    const keyed = Object.keys(state.reliability.ruleTripsByRule);
    assert.ok(keyed.length > 0, "fixture must carry ruleTripsByRule keys");
  });

  it("test_unavailable_degrades", () => {
    const reason = "the contract file is unreadable";
    const vm = buildRulebook({ available: false, reason }, initial());
    assert.deepEqual(vm, { available: false, reason });
    const html = rulebookPageHtml(vm);
    assert.match(html, /the contract file is unreadable/);
    assert.equal(html.includes("rulebook-card"), false);
    assert.equal(buildRulebook(null, initial()).available, false);
    assert.equal(buildRulebook({}, initial()).available, false);
  });

  it("test_pure", () => {
    const state = deepFreeze(fold(EVENTS));
    const payload = deepFreeze({ available: true, rules: loadRules() });
    const a = buildRulebook(payload, state);
    const b = buildRulebook(payload, state);
    assert.deepEqual(a, b);
  });

  it("test_page_statement_first", () => {
    const vm = buildRulebook(PAYLOAD, initial());
    const html = rulebookPageHtml(vm);
    const firstCard = html.match(/<section class="card rulebook-card">([\s\S]*?)<\/section>/);
    assert.ok(firstCard);
    const statementAt = firstCard[1].indexOf(PAYLOAD.rules[0].statement);
    const chipAt = firstCard[1].indexOf("chip-state");
    assert.ok(statementAt >= 0 && chipAt >= 0 && statementAt < chipAt);
    const header = DICT.rulebookHeader.word.replace("{n}", "18");
    assert.ok(html.includes(header));
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.match(src, /hash:\s*"the-rules"/);
    assert.match(src, /render:\s*renderRulebook/);
  });
});
