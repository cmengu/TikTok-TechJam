/** C1 copy.js dictionary tests — node --test, no DOM. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { STATES } from "./reducer.js";
import {
  BANNED,
  claimLabel,
  fmtDelta,
  fmtDuration,
  fmtScore,
  fmtTokens,
  levelLabel,
  moveLabel,
  rungLabel,
  stateLabel,
} from "./copy.js";

const GERUND_ALLOWLIST = new Set([
  "accepted",
  "declined",
  "retrying",
  "shelved",
  "disqualified",
  "crashed",
  "screening",
  "building",
  "repeating",
  "fixing",
]);

function bannedRe() {
  return new RegExp(`\\b(?:${BANNED.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "i");
}

describe("copy", () => {
  it("test_every_state_has_a_label", () => {
    for (const state of STATES) {
      const label = stateLabel(state);
      assert.equal(typeof label.word, "string");
      assert.ok(label.word.length > 0, `empty word for ${state}`);
      assert.ok(
        GERUND_ALLOWLIST.has(label.word),
        `${state} → ${label.word} not in gerund allowlist`,
      );
    }
  });

  it("test_unknown_term_passes_through", () => {
    assert.deepEqual(stateLabel("mystery"), { word: "mystery", hint: null });
    assert.deepEqual(moveLabel("warp"), { word: "warp", hint: null });
    assert.deepEqual(levelLabel("gamma"), { word: "gamma", hint: null });
    assert.deepEqual(rungLabel("ladder"), { word: "ladder", hint: null });
    assert.deepEqual(claimLabel("L9"), { word: "L9", hint: null });
  });

  it("test_labels_contain_no_banned_words", () => {
    const re = bannedRe();
    const samples = [
      ...STATES.map(stateLabel),
      moveLabel("draft"),
      moveLabel("improve"),
      moveLabel("debug"),
      moveLabel(null),
      levelLabel("omega"),
      levelLabel("v_sem"),
      levelLabel("smoke"),
      rungLabel("screen"),
      rungLabel("replicate"),
      claimLabel("L4-v"),
      claimLabel("L4-m"),
      claimLabel("L3"),
    ];
    for (const label of samples) {
      assert.equal(re.test(label.word), false, `banned in word: ${label.word}`);
      if (label.hint != null) {
        assert.equal(re.test(label.hint), false, `banned in hint: ${label.hint}`);
      }
    }
  });

  it("test_formatters", () => {
    assert.equal(fmtScore(0.60414), "0.6041");
    assert.equal(fmtScore(null), "—");
    assert.equal(fmtDelta(0.004), "+0.0040");
    assert.equal(fmtDelta(-0.002), "-0.0020");
    assert.equal(fmtDelta(null), "—");
    assert.equal(fmtTokens(12400), "12.4k");
    assert.equal(fmtDuration(94), "1m 34s");
  });

  it("test_zero_is_not_a_dash", () => {
    assert.equal(fmtScore(0), "0.0000");
    assert.equal(fmtTokens(0), "0");
    assert.notEqual(fmtScore(0), "—");
    assert.notEqual(fmtTokens(0), "—");
  });
});
