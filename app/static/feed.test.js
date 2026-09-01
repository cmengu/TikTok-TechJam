/** C2 feed.js sentence tests — node --test, fixture only (no DOM). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BANNED } from "./copy.js";
import { sentence } from "./feed.js";

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

function bannedRe() {
  return new RegExp(
    `\\b(?:${BANNED.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`,
    "i",
  );
}

describe("feed", () => {
  it("test_promoted_verdict_reads_accepted", () => {
    const ev = loadFixture().find(
      (e) => e.type === "verdict" && e.state === "promoted",
    );
    assert.ok(ev);
    const s = sentence(ev);
    assert.match(s, /accepted/i);
    assert.match(s, /hidden check/i);
    assert.match(s, /\+0\.0040/);
  });

  it("test_unclear_verdict_says_unexplained", () => {
    const ev = loadFixture().find(
      (e) => e.type === "verdict" && e.attribution === "unclear",
    );
    assert.ok(ev);
    assert.match(sentence(ev), /unexplained/i);
  });

  it("test_declined_and_retrying_read_plain", () => {
    const events = loadFixture().filter((e) => e.type === "verdict");
    const declined = events.find((e) => e.state === "rejected");
    const retrying = events.find(
      (e) => e.state === "inconclusive" && e.attribution == null,
    );
    assert.ok(declined);
    assert.ok(retrying);
    assert.match(sentence(declined), /declined/i);
    assert.match(sentence(retrying), /retrying/i);
  });

  it("test_every_fixture_event_renders", () => {
    for (const ev of loadFixture()) {
      const s = sentence(ev);
      assert.equal(typeof s, "string");
      assert.ok(s.length > 0, `empty sentence for ${ev.type} seq=${ev.seq}`);
    }
  });

  it("test_malformed_event_degrades", () => {
    assert.doesNotThrow(() => sentence(null));
    assert.doesNotThrow(() => sentence(undefined));
    assert.doesNotThrow(() => sentence({}));
    assert.doesNotThrow(() => sentence({ type: "verdict" }));
    assert.equal(typeof sentence(null), "string");
    assert.equal(typeof sentence({ type: "verdict" }), "string");
  });

  it("test_no_banned_words_in_any_sentence", () => {
    const re = bannedRe();
    for (const ev of loadFixture()) {
      const s = sentence(ev);
      assert.equal(re.test(s), false, `banned in: ${s}`);
    }
  });

  // --- the "unexplained win" sentence may fire ONLY on the attribution
  // branch (Unexplained_win_investigation.md §3). These four events are
  // verbatim slices of real runs where the old attribution-first check
  // narrated "passed the tests" over requeues and outright rejections. ---

  // runs/kuairand-20260831-171932 seq 68: seed-consistency requeue that
  // happens to carry attribution "unclear" — it did NOT pass the tests.
  const SEED_REQUEUE = {
    seq: 68,
    type: "verdict",
    node: 3,
    state: "inconclusive",
    metric: "primary",
    scores: [0.5864380773787898, 0.5874731888720104, 0.5877177397738794],
    seeds: [1, 2, 3],
    rung: "replicate",
    delta_mean: -0.00019035313849199062,
    delta_per_seed: [
      -0.002131286148191358, 0.0002306339008664171, 0.0013295928318489691,
    ],
    summary: "replicate seed consistency < 1; requeue",
    attribution: "unclear",
    producer: "measure",
  };

  // runs/kuairand-20260831-171932 seq 140: replicate fail, all seeds
  // negative — an outright rejection, also stamped "unclear".
  const REPLICATE_FAIL = {
    seq: 140,
    type: "verdict",
    node: 6,
    state: "rejected",
    metric: "primary",
    scores: [0.5825349827276163, 0.5808372205674142, 0.582056198607946],
    seeds: [1, 2, 3],
    rung: "replicate",
    delta_mean: -0.0055905545123930605,
    delta_per_seed: [
      -0.0060343807993649135, -0.006405334403729812, -0.004331948334084457,
    ],
    summary: "replicate fail_sign",
    attribution: "unclear",
    producer: "measure",
  };

  // runs/kuairand-20260831-180915 seq 24 and 35: screens rejected at
  // Δ −0.09 / −0.018 — nothing passed, yet both carry "unclear".
  const SCREEN_REJECTS = [
    {
      seq: 24,
      type: "verdict",
      node: 2,
      state: "rejected",
      metric: "primary",
      scores: [0.5046098149068092],
      seeds: [1],
      rung: "screen",
      delta_mean: -0.09178290894419483,
      delta_per_seed: [-0.09178290894419483],
      summary: "screen rejected: Δ=-0.0918",
      attribution: "unclear",
      producer: "measure",
    },
    {
      seq: 35,
      type: "verdict",
      node: 3,
      state: "rejected",
      metric: "primary",
      scores: [0.5779984215469511],
      seeds: [1],
      rung: "screen",
      delta_mean: -0.018394302304052923,
      delta_per_seed: [-0.018394302304052923],
      summary: "screen rejected: Δ=-0.0184",
      attribution: "unclear",
      producer: "measure",
    },
  ];

  it("test_seed_requeue_is_not_narrated_as_a_passed_win", () => {
    const s = sentence(SEED_REQUEUE);
    assert.doesNotMatch(s, /passed the tests/i);
    assert.doesNotMatch(s, /unexplained/i);
    assert.match(s, /retrying/i);
    assert.match(s, /didn't repeat across seeds/i);
  });

  it("test_replicate_fail_reads_declined_not_unexplained_win", () => {
    const s = sentence(REPLICATE_FAIL);
    assert.doesNotMatch(s, /passed the tests/i);
    assert.doesNotMatch(s, /unexplained/i);
    assert.match(s, /declined/i);
  });

  it("test_screen_rejections_read_declined_not_unexplained_win", () => {
    for (const ev of SCREEN_REJECTS) {
      const s = sentence(ev);
      assert.doesNotMatch(s, /passed the tests/i, `false pass in: ${s}`);
      assert.doesNotMatch(s, /unexplained/i, `false pass in: ${s}`);
      assert.match(s, /declined/i);
    }
  });

  it("test_true_attribution_hold_still_reads_unexplained", () => {
    // The one branch where the sentence is honest: replicate passed but the
    // win could not be explained (fixture seq 129 mirrors the real shape).
    const ev = loadFixture().find(
      (e) =>
        e.type === "verdict" &&
        /pass but attribution unclear/.test(e.summary || ""),
    );
    assert.ok(ev);
    const s = sentence(ev);
    assert.match(s, /passed the tests/i);
    assert.match(s, /unexplained/i);
    assert.match(s, /not accepted/i);
  });

  it("test_liveness_sentences_carry_no_banned_words", () => {
    const re = bannedRe();
    for (const ev of [SEED_REQUEUE, REPLICATE_FAIL, ...SCREEN_REJECTS]) {
      const s = sentence(ev);
      assert.equal(re.test(s), false, `banned in: ${s}`);
    }
  });
});
