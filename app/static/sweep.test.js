/** G1 jargon sweep — every view-model string leaf vs copy.js BANNED. */

import { readFileSync, readdirSync } from "node:fs";
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

// ── G1b — static scan of renderer template literals ──────────────────────────
// The leaf walk above covers view-model output; it cannot see jargon typed
// directly into a renderer's HTML template (the "Rung" heading shipped that
// way). This scan reads every non-test module's source, extracts template
// literal contents with a small state machine (comments, quotes, and ${…}
// interpolations excluded, nesting handled), and checks the *rendered* text —
// text nodes plus title/aria-label hover values — against the same BANNED list.

function extractTemplates(src) {
  const out = [];
  const mode = ["code"]; // code | tpl | interp | line | block | sq | dq
  const bufs = [];
  const depths = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const d = src[i + 1];
    const m = mode[mode.length - 1];
    if (m === "line") {
      if (c === "\n") mode.pop();
      i += 1;
    } else if (m === "block") {
      if (c === "*" && d === "/") {
        mode.pop();
        i += 2;
      } else i += 1;
    } else if (m === "sq" || m === "dq") {
      if (c === "\\") i += 2;
      else {
        if ((m === "sq" && c === "'") || (m === "dq" && c === '"')) mode.pop();
        i += 1;
      }
    } else if (m === "tpl") {
      if (c === "\\") {
        bufs[bufs.length - 1] += " ";
        i += 2;
      } else if (c === "`") {
        out.push(bufs.pop());
        mode.pop();
        i += 1;
      } else if (c === "$" && d === "{") {
        mode.push("interp");
        depths.push(0);
        bufs[bufs.length - 1] += "\x00";
        i += 2;
      } else {
        bufs[bufs.length - 1] += c;
        i += 1;
      }
    } else {
      // code or interp
      if (c === "/" && d === "/") {
        mode.push("line");
        i += 2;
      } else if (c === "/" && d === "*") {
        mode.push("block");
        i += 2;
      } else if (c === "'") {
        mode.push("sq");
        i += 1;
      } else if (c === '"') {
        mode.push("dq");
        i += 1;
      } else if (c === "`") {
        mode.push("tpl");
        bufs.push("");
        i += 1;
      } else if (m === "interp" && c === "{") {
        depths[depths.length - 1] += 1;
        i += 1;
      } else if (m === "interp" && c === "}") {
        if (depths[depths.length - 1] === 0) {
          mode.pop();
          depths.pop();
        } else depths[depths.length - 1] -= 1;
        i += 1;
      } else i += 1;
    }
  }
  return out;
}

// Rendered text a viewer can meet: hover values first, then text nodes with
// tags stripped; \x00 marks a removed interpolation so words never merge
// across it.
function visibleChunks(tpl) {
  const chunks = [];
  for (const m of tpl.matchAll(/(?:title|aria-label)="([^"]*)"/gi)) {
    chunks.push(...m[1].split("\x00"));
  }
  const text = tpl.replace(/<[^>]*>/g, " ");
  chunks.push(...text.split("\x00"));
  return chunks.map((s) => s.trim()).filter(Boolean);
}

describe("G1b static template scan", () => {
  const moduleFiles = readdirSync(__dirname).filter(
    (f) => f.endsWith(".js") && !f.endsWith(".test.js"),
  );
  const bannedRes = BANNED.map((t) => ({ term: t, re: new RegExp(`\\b${t}\\b`, "i") }));

  function collect() {
    const all = [];
    for (const file of moduleFiles) {
      const src = readFileSync(join(__dirname, file), "utf8");
      for (const tpl of extractTemplates(src)) {
        for (const chunk of visibleChunks(tpl)) all.push({ file, chunk });
      }
    }
    return all;
  }

  it("test_no_renderer_template_emits_banned_terms", () => {
    const violations = [];
    for (const { file, chunk } of collect()) {
      for (const { term, re } of bannedRes) {
        if (re.test(chunk)) violations.push(`${file}: "${chunk}" (${term})`);
      }
    }
    assert.deepEqual(violations, []);
  });

  it("test_template_scan_actually_covers", () => {
    // Refusal twin: a scanner that parses nothing passes vacuously. The
    // renderers carry well over a hundred rendered text chunks today.
    assert.ok(collect().length > 100, `only ${collect().length} chunks found`);
  });
});
