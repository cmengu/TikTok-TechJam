/** F1 trace.js event-count tests — node --test, fixture only (no DOM). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { TRACE_KEYS, buildTrace } from "./trace.js";

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

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

/*
 * Derivation against tests/fixtures/fake-events.jsonl (post-E4), counted
 * as events — not unique ids, not latest-verdict intentions.
 *
 *   python3 -c "import json; from collections import Counter
 *   ev=[json.loads(l) for l in open('tests/fixtures/fake-events.jsonl') if l.strip()]
 *   print(Counter(e['type'] for e in ev))
 *   v=[e for e in ev if e['type']=='verdict']
 *   print('screen', sum(1 for e in v if e.get('rung')=='screen'))
 *   print('replicate', sum(1 for e in v if e.get('rung')=='replicate'))
 *   print('holdout meas', sum(1 for e in ev if e['type']=='measurement' and e.get('rung')=='holdout'))
 *   print({s: sum(1 for e in v if e.get('state')==s) for s in
 *          ('promoted','rejected','inconclusive','retired','failed')})"
 *
 *   research_source 4          → papersRead
 *   hypothesis_queued 6        → ideasProposed
 *   proposal_rejected 1        → ideasBanned
 *   node_created 4             → attemptsBuilt
 *   verdict rung=screen 3      → quickTests  (two screens on one node would be 2)
 *   verdict rung=replicate 2   → repeatTests
 *   measurement rung=holdout 1 → hiddenChecks
 *   verdict state=promoted 1   → accepted
 *   verdict state=rejected 1   → declined
 *   verdict state=inconclusive 2 → retrying
 *   verdict state=retired 0    → shelved
 *   failure 2                  → crashed
 */
const FIXTURE_TRACE = {
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

describe("trace", () => {
  it("test_trace_counts_match_fixture", () => {
    const trace = buildTrace(fold(loadFixture()));
    assert.deepEqual(trace, FIXTURE_TRACE);
    assert.deepEqual(Object.keys(trace).sort(), [...TRACE_KEYS].sort());
  });

  it("test_trace_empty_state_all_zeros", () => {
    const trace = buildTrace(initial());
    for (const key of TRACE_KEYS) {
      assert.equal(trace[key], 0, key);
    }
  });

  it("test_trace_pure", () => {
    const state = fold(loadFixture());
    const before = structuredClone(state);
    const a = buildTrace(state);
    const b = buildTrace(state);
    assert.deepEqual(a, b);
    assert.deepEqual(state, before);
    assert.notEqual(a, b);
  });
});

// --- Fix-list item 1: llm.py's cost bookkeeping rides the research_source
// event type titled "llm usage"; the funnel must count real papers only. ---
describe("trace llm-usage de-pollution", () => {
  const LLM_USAGE = {
    schema_version: 1,
    seq: 9001,
    t: "2026-08-31T17:32:22.153Z",
    run: "kuairand-20260831-171932",
    type: "research_source",
    id: "usage-0-coding",
    title: "llm usage",
    node: 0,
    cost: { gpu_s: 0.0, tokens_in: 17244, tokens_out: 9069, slice: "coding" },
    summary: "llm coding: 17244 in / 9069 out tokens",
  };

  it("test_llm_usage_rows_do_not_count_as_papers", () => {
    const events = loadFixture();
    const clean = buildTrace(fold(events));
    const polluted = buildTrace(
      fold([...events, LLM_USAGE, { ...LLM_USAGE, seq: 9002, id: "usage-1-coding" }]),
    );
    assert.equal(polluted.papersRead, clean.papersRead);
  });

  it("test_real_papers_still_count", () => {
    const events = loadFixture();
    const real = {
      ...LLM_USAGE,
      seq: 9003,
      id: "src-99",
      title: "Factorization Machines",
      summary: "read",
    };
    const trace = buildTrace(fold([...events, real]));
    assert.equal(trace.papersRead, buildTrace(fold(events)).papersRead + 1);
  });
});
