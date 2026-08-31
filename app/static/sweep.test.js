/** G1 jargon sweep — every view-model string leaf vs copy.js BANNED. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BANNED } from "./copy.js";
import { initial, reduce, ideaOutcome } from "./reducer.js";
import { buildTrace } from "./trace.js";
import { buildTree, moveTargets } from "./tree.js";
import { buildDossier, buildAttemptTrail } from "./dossier.js";
import { buildJourney, journeyStripHtml } from "./journey.js";
import { sentence, buildMoveTrail } from "./feed.js";
import { buildLibrary, libraryPageHtml } from "./library.js";
import { buildIdeas, ideasPageHtml } from "./ideas.js";
import { buildBrief, briefPageHtml } from "./brief.js";
import {
  buildDoubleChecks,
  buildSpend,
  buildStability,
  doubleChecksPageHtml,
  spendPageHtml,
  stabilityPageHtml,
} from "./audit.js";
import {
  buildRung,
  buildLastMove,
  buildCascadeCounter,
  buildHero,
} from "./dashboard.js";
import { buildMonitors } from "./monitors.js";
import { buildReport, buildReportHero, reportPageHtml } from "./report.js";
import { chipHtml } from "./chip.js";
import { verdictReading, verdictAnnotation } from "./band.js";
import { stateLabel, claimLabel } from "./copy.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "fake-events.jsonl",
);
const MANIFEST = join(__dirname, "..", "..", "papers", "manifest.json");

function loadJsonl(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

const bannedRe = new RegExp(
  `\\b(?:${BANNED.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`,
  "i",
);

/**
 * Recursively collect string leaves. Keys named `source` or `id` are exempt
 * (they cite harness code paths by design).
 *
 * Additional exemptions, each with a reason:
 * - `node`, `verdict`, `move`: pass-through harness records. The page reads
 *   the translated fields (plainState, sentence, edgeLabel), not these.
 * - `rung`: harness comparison id on a band reading; displayed via rungLabel.
 * - `href`: load-bearing hash routes (A2: data-route unchanged). `#/hypotheses`
 *   is the route name, not displayed copy — the funnel label is "ideas".
 */
const EXEMPT_KEYS = new Set(["source", "id", "node", "verdict", "move", "rung", "href"]);

function walk(value, key, out) {
  if (value == null) return;
  if (EXEMPT_KEYS.has(key)) return;
  if (typeof value === "string") {
    out.push(value);
    return;
  }
  if (typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (const item of value) walk(item, key, out);
    return;
  }
  for (const [k, v] of Object.entries(value)) walk(v, k, out);
}

const MONITORS = {
  available: true,
  primary: 0.527,
  spread: 0.001,
  oracle_gap: [[3, 0.027]],
  gap_alarm: false,
  seed_consistency: [[3, 1.0]],
  rank_corr: null,
  ladder_queries: 1,
  claim_level: "L4-v",
  claim_reason: "1 of 1 promotions carry oracle_delta",
};

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
  training: { tokens_in: 0.0, tokens_out: 0.0, gpu_h: 0.1867 },
  tuning: { tokens_in: 30.0, tokens_out: 10.0, gpu_h: 0.0 },
};

const RELIABILITY = {
  failures_by_class: { cuda_oom: 1, stall: 1 },
  recoveries: { ok: 2, failed: 0 },
  time_to_first_valid_submission_s: 0.002,
  longest_unattended_s: 0.002,
  rule_trips: 2,
};

function collectLeaves() {
  const events = loadJsonl(FIXTURE);
  const state = fold(events);
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
  const trace = buildTrace(state);
  const out = [];

  const views = [
    trace,
    buildTree(state),
    moveTargets(state),
    buildDossier(state, 3),
    buildAttemptTrail(state, 3),
    buildAttemptTrail(state, 1),
    buildJourney(state, 3),
    journeyStripHtml(buildJourney(state, 3)),
    buildMoveTrail(state),
    buildLibrary(state, manifest),
    libraryPageHtml(buildLibrary(state, manifest)),
    buildIdeas(state),
    ideasPageHtml(buildIdeas(state)),
    buildBrief({
      available: true,
      task: "synthetic",
      sections: [{ title: "The goal", body: "Beat the current best." }],
    }),
    briefPageHtml(
      buildBrief({
        available: true,
        task: "synthetic",
        sections: [{ title: "The goal", body: "Beat the current best." }],
      }),
    ),
    buildDoubleChecks(REPLICATION),
    doubleChecksPageHtml(buildDoubleChecks(REPLICATION)),
    buildSpend(COST),
    spendPageHtml(buildSpend(COST)),
    buildStability(RELIABILITY),
    stabilityPageHtml(buildStability(RELIABILITY)),
    buildRung(MONITORS),
    buildLastMove(state),
    buildCascadeCounter(state),
    buildHero(MONITORS, trace),
    buildMonitors(MONITORS),
    buildReport({ available: true, markdown: "# Run report\n\nDone.\n" }),
    buildReportHero(MONITORS),
    reportPageHtml(
      buildReport({ available: true, markdown: "# Run report\n\nDone.\n" }),
      buildReportHero(MONITORS),
    ),
    chipHtml(stateLabel("promoted"), "accepted"),
    chipHtml(claimLabel("L4-v"), null),
    ideaOutcome(state, "h-train-1") && stateLabel(ideaOutcome(state, "h-train-1").state),
  ];

  for (const ev of events) {
    views.push(sentence(ev));
    if (ev.type === "verdict") {
      views.push(verdictReading(ev));
      views.push(verdictAnnotation(ev));
    }
  }

  for (const view of views) walk(view, null, out);
  return out;
}

describe("sweep", () => {
  it("test_no_view_emits_banned_terms", () => {
    const leaves = collectLeaves();
    const hits = leaves.filter((s) => bannedRe.test(s));
    assert.deepEqual(hits, [], hits.slice(0, 20).join(" | "));
  });

  it("test_sweep_actually_covers", () => {
    const leaves = collectLeaves();
    assert.ok(leaves.length > 100, `walker found ${leaves.length} string leaves`);
  });
});
