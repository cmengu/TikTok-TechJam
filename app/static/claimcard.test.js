/** V5 claim card tests — node --test, fixture only. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { DICT } from "./copy.js";
import { buildClaimCard, claimCardHtml } from "./claimcard.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INDEX = join(__dirname, "index.html");
const FIXTURE = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");

function fold() {
  return readFileSync(FIXTURE, "utf8")
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

describe("claimcard", () => {
  it("test_rows_from_observables", () => {
    const card = buildClaimCard(fold(), 3);
    assert.ok(card);
    assert.equal(card.mechanism, "lr-schedule");
    assert.equal(card.verdict, "given");
    assert.equal(card.rows[0].name, "gauc");
    assert.equal(card.rows[0].mustMove, DICT.claimMustUp.word);
    assert.equal(card.rows[0].moved, DICT.claimMovedYes.word);
  });

  it("test_refused_verdict_sentence", () => {
    const card = buildClaimCard(fold(), 4);
    assert.equal(card.verdict, "refused");
    assert.equal(card.sentence, DICT.claimRefusedSentence.word);
    assert.ok(claimCardHtml(card).includes(DICT.claimRefusedSentence.word));
  });

  it("test_moved_null_reads_not_measured", () => {
    const state = {
      ...initial(),
      attribution: {
        byNode: {
          9: {
            mechanism: "x",
            result: "clear",
            observables: [{ name: "gauc", direction: "positive", moved: null }],
          },
        },
      },
    };
    const card = buildClaimCard(state, 9);
    assert.equal(card.rows[0].moved, DICT.claimNotMeasured.word);
  });

  it("test_no_attribution_no_card", () => {
    assert.equal(buildClaimCard(fold(), 1), null);
    assert.equal(claimCardHtml(null), "");
  });

  it("test_refused_equal_prominence", () => {
    const css = readFileSync(INDEX, "utf8");
    const given = css.match(/\.claim-banner--given\s*\{([^}]+)\}/);
    const refused = css.match(/\.claim-banner--refused\s*\{([^}]+)\}/);
    assert.ok(given && refused);
    const size = (block) => (block.match(/font-size:\s*([^;]+)/) || [])[1];
    const weight = (block) => (block.match(/font-weight:\s*([^;]+)/) || [])[1];
    assert.equal(size(given[1]), size(refused[1]));
    assert.equal(weight(given[1]), weight(refused[1]));
    assert.match(refused[1], /var\(--wine\)/);
    assert.match(given[1], /var\(--pos\)/);
  });

  it("test_pure", () => {
    const state = deepFreeze(fold());
    assert.deepEqual(buildClaimCard(state, 3), buildClaimCard(state, 3));
  });
});
