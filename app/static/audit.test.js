/** E7 audit view-model tests — node --test, canned payloads (no fetch). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildDoubleChecks, buildSpend, buildStability, spendPageHtml } from "./audit.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");

const REPLICATION = [
  {
    node: 1,
    screen_vs_full: null,
    one_vs_many_seeds: null,
    searchval_vs_holdout: null,
  },
  {
    node: 3,
    screen_vs_full: -0.002,
    one_vs_many_seeds: -0.002,
    searchval_vs_holdout: 0.002,
  },
];

const COST = {
  researching: { tokens_in: 100.0, tokens_out: 40.0, gpu_h: 0.0 },
  coding: { tokens_in: 100.0, tokens_out: 40.0, gpu_h: 0.0 },
  training: { tokens_in: 0.0, tokens_out: 0.0, gpu_h: 0.18666666666666665 },
  tuning: { tokens_in: 30.0, tokens_out: 10.0, gpu_h: 0.0 },
};

const RELIABILITY = {
  failures_by_class: { cuda_oom: 1, stall: 1 },
  recoveries: { ok: 2, failed: 0 },
  time_to_first_valid_submission_s: 0.002,
  longest_unattended_s: 0.002,
  rule_trips: 2,
};

describe("audit", () => {
  it("test_doublecheck_rows_and_verdicts", () => {
    const vm = buildDoubleChecks(REPLICATION);
    assert.equal(vm.rows.length, 2);
    const n3 = vm.rows.find((r) => r.node === 3);
    assert.equal(n3.quickVsRepeatVerdict, "shrank");
    assert.equal(n3.oneVsManyVerdict, "shrank");
    assert.equal(n3.repeatVsHiddenVerdict, "held up");
    const n1 = vm.rows.find((r) => r.node === 1);
    assert.equal(n1.quickVsRepeatVerdict, null);
  });

  it("test_spend_echoes_payload", () => {
    const vm = buildSpend(COST);
    assert.equal(vm.slices.length, 4);
    const papers = vm.slices.find((s) => s.slice === "researching");
    assert.equal(papers.label, "reading papers");
    assert.equal(papers.tokens_in, COST.researching.tokens_in);
    assert.equal(papers.tokens_out, COST.researching.tokens_out);
    assert.equal(papers.gpu_h, COST.researching.gpu_h);
    const testing = vm.slices.find((s) => s.slice === "training");
    assert.equal(testing.label, "testing");
    assert.equal(testing.gpu_h, COST.training.gpu_h);
  });

  it("test_stability_fields", () => {
    const vm = buildStability(RELIABILITY);
    assert.deepEqual(
      vm.crashes.map((c) => c.kind).sort(),
      ["cuda_oom", "stall"],
    );
    assert.equal(vm.rescued, 2);
    assert.equal(vm.rulebookTrips, 2);
    assert.equal(vm.longestUnattendedS, 0.002);
  });

  it("test_all_three_null_on_malformed", () => {
    assert.equal(buildDoubleChecks(null), null);
    assert.equal(buildDoubleChecks({}), null);
    assert.equal(buildSpend(null), null);
    assert.equal(buildSpend({ researching: {} }), null);
    assert.equal(buildStability(null), null);
    assert.equal(buildStability({ failures_by_class: {} }), null);
  });

  it("test_routes_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Audit — Replication")'), false);
    assert.equal(src.includes('renderStub("Audit — Cost")'), false);
    assert.equal(src.includes('renderStub("Audit — Reliability")'), false);
    assert.match(src, /render:\s*renderDoubleChecks/);
    assert.match(src, /render:\s*renderSpend/);
    assert.match(src, /render:\s*renderStability/);
  });
});

describe("spend page html", () => {
  it("test_ledger_keys_live_on_the_hover_only", () => {
    // Fix list item 10: "researching.tokens_in" was printed under each number.
    const html = spendPageHtml(buildSpend(COST));
    assert.ok(html.includes('title="researching.tokens_in"'));
    assert.ok(!html.includes(">researching.tokens_in<"));
    assert.ok(!html.includes("stat-src"));
    assert.ok(html.includes("reading papers"));
  });
});

describe("spend page folds structural zeros", () => {
  // Fix list item 12: "0 reading papers / 111145 writing code / 0 testing /
  // 0 tuning" reads as broken data. The researcher never ran, and testing/
  // tuning carry no words by design (testing's real spend is GPU time).
  const CODING_ONLY = {
    researching: { tokens_in: 0.0, tokens_out: 0.0, gpu_h: 0.0 },
    coding: { tokens_in: 111145.0, tokens_out: 40210.0, gpu_h: 0.0 },
    training: { tokens_in: 0.0, tokens_out: 0.0, gpu_h: 0.008137365219687732 },
    tuning: { tokens_in: 0.0, tokens_out: 0.0, gpu_h: 0.0 },
  };

  it("test_primary_rows_are_only_the_slices_with_words", () => {
    const html = spendPageHtml(buildSpend(CODING_ONLY));
    const primary = html.split("<details")[0];
    assert.ok(primary.includes('title="coding.tokens_in"'));
    assert.ok(primary.includes("111145"));
    assert.equal(primary.includes('title="researching.tokens_in"'), false);
    assert.equal(primary.includes('title="training.tokens_in"'), false);
    assert.equal(primary.includes('title="tuning.tokens_in"'), false);
  });

  it("test_one_plain_line_for_gpu_time", () => {
    const html = spendPageHtml(buildSpend(CODING_ONLY));
    const primary = html.split("<details")[0];
    // 0.008137 h ≈ 29s through fmtDuration — a duration, not a bare 0.0.
    assert.ok(primary.includes("29s of GPU time"));
  });

  it("test_fold_keeps_the_full_breakdown_with_honest_hints", () => {
    const html = spendPageHtml(buildSpend(CODING_ONLY));
    assert.ok(html.includes("<details"));
    const fold = html.slice(html.indexOf("<details"));
    assert.ok(fold.includes("all four stages"));
    assert.ok(fold.includes("reading papers"));
    assert.ok(fold.includes("writing code"));
    assert.ok(fold.includes("testing"));
    assert.ok(fold.includes("tuning"));
    // Zero rows say why they are zero instead of looking broken.
    assert.ok(fold.includes("this stage has not run yet"));
    assert.ok(fold.includes("this stage spends computer time, not words"));
  });
});
