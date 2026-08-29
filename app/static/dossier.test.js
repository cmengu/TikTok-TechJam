/** Checkpoint 3 node dossier tests — node --test, fixtures only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildDossier } from "./dossier.js";
import { verdictReading } from "./band.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REAL_VERDICT_FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "real-verdict.jsonl",
);

function loadJsonl(path) {
  const text = readFileSync(path, "utf8");
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

// tests/fixtures/real-verdict.jsonl carries a screen verdict (seq 1), a
// replicate verdict (seq 2) and a prediction (seq 3), all for node 7 — see
// band.test.js's header comment for its provenance. The dossier only reads
// state.verdicts (populated by the reducer's "verdict" case), which never
// holds "prediction" events, so only the two verdict lines are relevant
// here; the fixture's prediction line is loaded along with them but plays
// no part in buildDossier's output.
function loadRealVerdictEvents() {
  return loadJsonl(REAL_VERDICT_FIXTURE).filter((ev) => ev.type === "verdict");
}

function makeNode(id, extra = {}) {
  return {
    id,
    parent: null,
    kind: "draft",
    hypothesisId: `h-${id}`,
    state: "screening",
    stateHistory: [{ state: "screening", seq: 1, t: "2026-08-28T00:00:00.000Z" }],
    scores: {},
    seeds: [],
    bands: {},
    latestVerdict: null,
    failures: [],
    recoveries: [],
    ruleTrips: [],
    createdSeq: 1,
    ...extra,
  };
}

function makeState(nodes, verdicts = []) {
  return { nodes, nodeOrder: Object.keys(nodes), verdicts, incumbent: null };
}

describe("dossier — buildDossier, node with several verdicts", () => {
  it("test_verdicts_ordered_newest_first", () => {
    const verdictEvents = loadRealVerdictEvents();
    assert.equal(verdictEvents.length, 2, "expected exactly two verdict events in the fixture");
    const state = makeState({ 7: makeNode(7) }, verdictEvents);

    const dossier = buildDossier(state, "7");
    assert.ok(dossier, "expected a dossier for node 7");
    assert.equal(dossier.node.id, 7);
    assert.equal(dossier.verdicts.length, 2);
    // seq 2 (promoted, replicate) must come before seq 1 (inconclusive, screen).
    assert.equal(dossier.verdicts[0].verdict.seq, 2);
    assert.equal(dossier.verdicts[0].verdict.state, "promoted");
    assert.equal(dossier.verdicts[1].verdict.seq, 1);
    assert.equal(dossier.verdicts[1].verdict.state, "inconclusive");
  });

  it("test_each_verdict_reading_matches_bandjs_directly", () => {
    // dossier.js must not reimplement band logic — it calls band.js's own
    // verdictReading and hands the result through unchanged.
    const verdictEvents = loadRealVerdictEvents();
    const state = makeState({ 7: makeNode(7) }, verdictEvents);
    const dossier = buildDossier(state, "7");
    for (const { verdict, reading } of dossier.verdicts) {
      assert.deepEqual(reading, verdictReading(verdict));
    }
    const promoted = dossier.verdicts.find((v) => v.verdict.state === "promoted");
    assert.equal(promoted.reading.shape, "measure");
    assert.equal(promoted.reading.thresholdLabel, "bar");
    assert.equal(promoted.reading.side, "above");
    const screening = dossier.verdicts.find((v) => v.verdict.state === "inconclusive");
    assert.equal(screening.reading.thresholdLabel, "sd_delta_screen");
    assert.equal(screening.reading.side, "below");
  });

  it("test_string_node_id_matches_numeric_verdict_node_field", () => {
    // node ids arrive as numbers from node_created (state.nodes key / ev.node)
    // but reach buildDossier as strings from the URL — String() must bridge
    // both sides, the same way tree.js's hasNode does.
    const verdictEvents = loadRealVerdictEvents();
    for (const ev of verdictEvents) assert.equal(typeof ev.node, "number");
    const state = makeState({ 7: makeNode(7) }, verdictEvents);
    const dossier = buildDossier(state, "7"); // "7", not 7
    assert.equal(dossier.verdicts.length, 2);
  });
});

describe("dossier — buildDossier, node with no verdicts", () => {
  it("test_node_with_empty_verdicts_array", () => {
    const state = makeState({ 3: makeNode(3) }, []);
    const dossier = buildDossier(state, "3");
    assert.ok(dossier);
    assert.equal(dossier.node.id, 3);
    assert.deepEqual(dossier.verdicts, []);
  });

  it("test_node_with_only_other_nodes_verdicts", () => {
    const verdictEvents = loadRealVerdictEvents(); // all for node 7
    const state = makeState({ 3: makeNode(3), 7: makeNode(7) }, verdictEvents);
    const dossier = buildDossier(state, "3");
    assert.ok(dossier);
    assert.deepEqual(dossier.verdicts, []);
  });
});

describe("dossier — buildDossier, unknown id", () => {
  it("test_unknown_id_returns_null", () => {
    const state = makeState({ 3: makeNode(3) }, []);
    assert.equal(buildDossier(state, "404"), null);
  });

  it("test_null_and_undefined_id_return_null", () => {
    const state = makeState({ 3: makeNode(3) }, []);
    assert.equal(buildDossier(state, null), null);
    assert.equal(buildDossier(state, undefined), null);
  });
});

describe("dossier — buildDossier, verdict carrying attribution and rule_trips", () => {
  it("test_attribution_and_rule_trips_pass_through_unchanged", () => {
    // harness/measure.py:438-441 — a verdict payload carries "attribution"
    // and "rule_trips" only when present; dossier.js must not drop or
    // reinterpret them.
    const leaked = {
      type: "verdict",
      node: 9,
      seq: 5,
      t: "2026-08-28T00:05:00.000Z",
      state: "leaked",
      metric: "cvr_auc",
      scores: [0.6],
      seeds: [1],
      band: {
        sigma_screen: 0.02,
        sigma_full: 0.012,
        sigma_pair: 0.01,
        ratio: 0.6,
        rho: 0.8,
        sd_delta_screen: 0.012649,
        sd_delta_full: 0.007589,
        bar: 0.01,
        source: "fixed_pair",
        n_replicated: 1,
      },
      rung: "replicate",
      delta_mean: 0.02,
      delta_per_seed: [0.02],
      attribution: "unclear",
      rule_trips: ["no_test_peek"],
      summary: "replicate leaked: no_test_peek",
    };
    const state = makeState({ 9: makeNode(9) }, [leaked]);
    const dossier = buildDossier(state, "9");
    assert.equal(dossier.verdicts.length, 1);
    const { verdict, reading } = dossier.verdicts[0];
    assert.equal(verdict.attribution, "unclear");
    assert.deepEqual(verdict.rule_trips, ["no_test_peek"]);
    // reading itself is band.js's ordinary output — attribution/rule_trips
    // are not band fields, so they only ever surface via the raw verdict.
    assert.equal(reading.shape, "measure");
  });

  it("test_verdict_without_attribution_or_rule_trips_has_neither_key", () => {
    const verdictEvents = loadRealVerdictEvents();
    const state = makeState({ 7: makeNode(7) }, verdictEvents);
    const dossier = buildDossier(state, "7");
    for (const { verdict } of dossier.verdicts) {
      assert.equal(Object.prototype.hasOwnProperty.call(verdict, "attribution"), false);
      assert.equal(Object.prototype.hasOwnProperty.call(verdict, "rule_trips"), false);
    }
  });
});

describe("dossier — buildDossier, node's own failures/recoveries/ruleTrips/scores/seeds", () => {
  it("test_reliability_and_score_arrays_pass_through_from_the_node", () => {
    const failure = { type: "failure", node: 4, class: "cuda_oom", summary: "s", seq: 2, t: "x" };
    const recovery = {
      type: "recovery",
      node: 4,
      class: "cuda_oom",
      action: "halve_batch",
      summary: "s",
      seq: 3,
      t: "x",
    };
    const ruleTrip = { type: "rule_trip", node: 4, rule: "no_test_peek", summary: "s", seq: 4, t: "x" };
    const node = makeNode(4, {
      failures: [failure],
      recoveries: [recovery],
      ruleTrips: [ruleTrip],
      scores: { cvr_auc: [0.5, 0.51] },
      seeds: [1, 2],
    });
    const state = makeState({ 4: node }, []);
    const dossier = buildDossier(state, "4");
    assert.deepEqual(dossier.node.failures, [failure]);
    assert.deepEqual(dossier.node.recoveries, [recovery]);
    assert.deepEqual(dossier.node.ruleTrips, [ruleTrip]);
    assert.deepEqual(dossier.node.scores, { cvr_auc: [0.5, 0.51] });
    assert.deepEqual(dossier.node.seeds, [1, 2]);
  });

  it("test_full_state_history_passes_through_from_the_node", () => {
    const history = [
      { state: "screening", seq: 1, t: "a" },
      { state: "running", seq: 2, t: "b" },
      { state: "promoted", seq: 3, t: "c" },
    ];
    const node = makeNode(4, { stateHistory: history, state: "promoted" });
    const state = makeState({ 4: node }, []);
    const dossier = buildDossier(state, "4");
    assert.deepEqual(dossier.node.stateHistory, history);
  });
});

describe("dossier — buildDossier, malformed state: never throws, returns null", () => {
  it("test_never_throws_on_malformed_input", () => {
    const inputs = [
      [null, "7"],
      [undefined, "7"],
      [42, "7"],
      ["state", "7"],
      [[], "7"],
      [{}, "7"],
      [{ nodes: null }, "7"],
      [{ nodes: undefined }, "7"],
      [{ nodes: "garbage" }, "7"],
      [{ nodes: [] }, "7"],
      [{ nodes: { 7: null } }, "7"],
      [{ nodes: { 7: "not an object" } }, "7"],
      [{ nodes: { 7: [] } }, "7"],
      [{ nodes: { 7: makeNode(7) }, verdicts: "garbage" }, "7"],
      [{ nodes: { 7: makeNode(7) }, verdicts: null }, "7"],
      [{ nodes: { 7: makeNode(7) }, verdicts: [null, 5, "x", { no: "node field" }] }, "7"],
      [{ nodes: { 7: makeNode(7) } }, null],
      [{ nodes: { 7: makeNode(7) } }, undefined],
      [makeState({ 7: makeNode(7) }), {}],
      [makeState({ 7: makeNode(7) }), []],
    ];
    for (const [state, nodeId] of inputs) {
      assert.doesNotThrow(
        () => buildDossier(state, nodeId),
        `threw on state=${JSON.stringify(state)} nodeId=${JSON.stringify(nodeId)}`,
      );
    }
  });

  it("test_malformed_state_without_the_node_returns_null", () => {
    const inputs = [
      [null, "7"],
      [undefined, "7"],
      [42, "7"],
      ["state", "7"],
      [[], "7"],
      [{}, "7"],
      [{ nodes: null }, "7"],
      [{ nodes: "garbage" }, "7"],
      [{ nodes: { 7: null } }, "7"],
      [{ nodes: { 7: "not an object" } }, "7"],
    ];
    for (const [state, nodeId] of inputs) {
      assert.equal(buildDossier(state, nodeId), null);
    }
  });

  it("test_malformed_verdict_entries_are_skipped_not_thrown", () => {
    const state = makeState({ 7: makeNode(7) }, [null, 5, "x", { no: "node field" }, { node: 7, seq: 1 }]);
    const dossier = buildDossier(state, "7");
    assert.ok(dossier);
    assert.equal(dossier.verdicts.length, 1);
    assert.equal(dossier.verdicts[0].verdict.node, 7);
  });
});
