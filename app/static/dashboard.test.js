/** F2 dashboard strip view-model tests — node --test, no DOM, no fetch. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildRung, buildLastMove, buildCascadeCounter, buildHero, heroHtml } from "./dashboard.js";

function move(round, kind, parent, reason) {
  return { type: "move_selected", round, kind, parent, reason };
}

describe("dashboard strip builders", () => {
  it("test_rung_badge_shows_level_and_reason", () => {
    const rung = buildRung({
      available: true,
      claim_level: "L4-v",
      claim_reason: "1 of 1 promotions carry oracle_delta",
    });
    assert.equal(rung.level, "L4-v");
    assert.equal(rung.reason, "1 of 1 accepted wins carry a hidden-check reading");
  });

  it("test_rung_badge_is_a_dash_while_unavailable", () => {
    const rung = buildRung({ available: false, claim_level: "L4-v" });
    assert.equal(rung.level, "—");
    assert.notEqual(rung.level, "L4");
    assert.notEqual(rung.level, 0);
    assert.ok(!JSON.stringify(rung).includes("L4"));
    assert.ok(!Object.values(rung).includes(0));
  });

  it("test_last_move_reads_the_newest_move", () => {
    const state = {
      moves: [
        move(0, "draft", null, "breadth floor"),
        move(1, "draft", null, "breadth floor"),
        move(2, "improve", 3, "extend best"),
      ],
    };
    const last = buildLastMove(state);
    assert.equal(last.round, 2);
    assert.equal(last.kind, "improve");
    assert.equal(last.parent, 3);
    assert.equal(last.reason, "extend best");
  });

  it("test_last_move_null_kind_renders_a_dash", () => {
    const last = buildLastMove({
      moves: [move(4, null, null, "at branch cap")],
    });
    assert.equal(last.kind, "—");
    assert.equal(last.parent, "—");
    assert.ok(!JSON.stringify(last).includes("null"));
  });

  it("test_cascade_counter_totals_llm_calls_and_runs", () => {
    const counter = buildCascadeCounter({
      cascade: {
        byNode: {
          1: [{ level: "omega", passed: true, llm_calls: 0, runs: 1 }],
          2: [{ level: "v_sem", passed: true, llm_calls: 1, runs: 2 }],
        },
        rejected: { omega: 0, v_sem: 0, smoke: 0 },
        counters: { llmCalls: 1, runs: 3 },
      },
    });
    assert.equal(counter.llmCalls, 1);
    assert.equal(counter.runs, 3);
  });

  it("test_cascade_counter_shows_zero_as_zero", () => {
    const counter = buildCascadeCounter({
      cascade: {
        byNode: {
          2: [{ level: "omega", passed: false, llm_calls: 0, runs: 0 }],
        },
        rejected: { omega: 1, v_sem: 0, smoke: 0 },
        counters: { llmCalls: 0, runs: 0 },
      },
    });
    assert.equal(counter.llmCalls, 0);
    assert.equal(typeof counter.llmCalls, "number");
    assert.notEqual(counter.llmCalls, null);
    assert.notEqual(counter.llmCalls, "—");
  });

  it("test_cascade_counter_splits_rejections_by_level", () => {
    const counter = buildCascadeCounter({
      cascade: {
        byNode: {},
        rejected: { omega: 2, v_sem: 1, smoke: 3 },
        counters: { llmCalls: 0, runs: 0 },
      },
    });
    assert.equal(counter.rejected.omega, 2);
    assert.equal(counter.rejected.v_sem, 1);
    assert.equal(counter.rejected.smoke, 3);
  });

  it("test_builders_are_pure", () => {
    const payload = {
      available: true,
      claim_level: "L4-v",
      claim_reason: "1 of 1 promotions carry oracle_delta",
    };
    const state = {
      moves: [move(0, "draft", null, "breadth floor")],
      cascade: {
        byNode: {},
        rejected: { omega: 0, v_sem: 0, smoke: 0 },
        counters: { llmCalls: 0, runs: 0 },
      },
    };
    const payloadBefore = structuredClone(payload);
    const stateBefore = structuredClone(state);
    assert.deepEqual(buildRung(payload), buildRung(payload));
    assert.deepEqual(buildLastMove(state), buildLastMove(state));
    assert.deepEqual(buildCascadeCounter(state), buildCascadeCounter(state));
    assert.deepEqual(payload, payloadBefore);
    assert.deepEqual(state, stateBefore);
  });
});

const TRACE = {
  papersRead: 4,
  ideasProposed: 6,
  ideasBanned: 1,
  attemptsBuilt: 4,
  quickTests: 3,
  repeatTests: 2,
  hiddenChecks: 1,
  accepted: 1,
  declined: 1,
  retrying: 2,
  shelved: 0,
  crashed: 2,
};

const MONITORS = {
  available: true,
  primary: 0.527,
  claim_level: "L4-v",
  claim_reason: "1 of 1 promotions carry oracle_delta",
};

describe("dashboard hero", () => {
  it("test_hero_shows_score_and_trust", () => {
    const hero = buildHero(MONITORS, TRACE);
    assert.equal(hero.score, "0.5270");
    assert.equal(hero.trust.word, "fully verified");
    assert.equal(typeof hero.trust.hint, "string");
  });

  it("test_hero_before_first_score", () => {
    const hero = buildHero({ available: false, primary: 0 }, TRACE);
    assert.equal(hero.score, "—");
    assert.notEqual(hero.score, "0.0000");
    assert.ok(Array.isArray(hero.funnel));
    assert.equal(hero.funnel.length, 4);
  });

  it("test_funnel_from_trace", () => {
    const hero = buildHero(MONITORS, TRACE);
    assert.deepEqual(
      hero.funnel.map((s) => [s.label, s.count, s.href]),
      [
        ["papers", 4, "#/research"],
        ["ideas", 6, "#/hypotheses"],
        ["attempts", 4, "#/run"],
        ["accepted", 1, "#/run"],
      ],
    );
  });

  it("test_caption_translates_the_harness_vocabulary", () => {
    // Fix list item 4: "no promotions on the log" reached the viewer.
    const hero = buildHero(MONITORS, TRACE);
    assert.equal(hero.caption, "1 of 1 accepted wins carry a hidden-check reading");
    const empty = buildHero(
      { ...MONITORS, claim_reason: "no promotions on the log" },
      TRACE,
    );
    assert.equal(empty.caption, "no accepted wins on the log yet");
  });

  it("test_caption_passes_unknown_reasons_through", () => {
    const hero = buildHero(
      { ...MONITORS, claim_reason: "something new the harness said" },
      TRACE,
    );
    assert.equal(hero.caption, "something new the harness said");
  });
});

describe("dashboard hero html", () => {
  it("test_hero_before_first_measurement_has_no_stamp", () => {
    // Fix list item 2: "\u2014 / measured" claimed provenance for a number
    // that does not exist yet.
    const hero = buildHero({ available: false }, TRACE);
    const html = heroHtml(hero);
    assert.ok(html.includes("\u2014"));
    assert.ok(!html.includes("stamp"));
    assert.ok(!html.includes("measured"));
  });

  it("test_hero_source_is_plain_language_with_raw_key_on_hover", () => {
    // Fix list item 3: the literal "monitors.primary" reached the viewer.
    const html = heroHtml(buildHero(MONITORS, TRACE));
    assert.ok(html.includes("from the measurement layer"));
    assert.ok(html.includes('title="monitors.primary"'));
    assert.ok(!html.includes(">monitors.primary<"));
  });

  it("test_hero_with_a_score_keeps_the_stamp", () => {
    const html = heroHtml(buildHero(MONITORS, TRACE));
    assert.ok(html.includes("0.5270"));
    assert.ok(html.includes('class="stamp stamp--measured"'));
  });
});
