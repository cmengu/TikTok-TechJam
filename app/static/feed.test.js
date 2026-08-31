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
});
