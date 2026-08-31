/** D1 — seven-stage attempt journey as a pure fold. No DOM. */

import { stateLabel, DICT } from "./copy.js";
import { escapeHtml } from "./chip.js";

export const STAGES = [
  { id: "idea", label: "idea" },
  { id: "free-checks", label: "free checks" },
  { id: "build", label: "build" },
  { id: "quick-test", label: "quick test" },
  { id: "repeat-test", label: "repeat test" },
  { id: "hidden-check", label: "hidden check" },
  { id: "decision", label: "decision" },
];

const LIVE_STATES = new Set([
  "screening",
  "running",
  "replicating",
  "debugging",
]);

/**
 * buildJourney(state, nodeId) → { stages, loops, decision } | null
 *
 * Fixture-adjusted rules (fake-events.jsonl is authority):
 * - free checks absent but node already has a screen/replicate verdict → done
 *   (scripted run skipped verify_level for nodes 3–4); else absent → skipped.
 * - hidden check done if any verdict carries oracle_delta OR attribution
 *   (node 4 has no oracle_delta but attribution "unclear").
 */
export function buildJourney(state, nodeId) {
  if (!state?.nodes) return null;
  const node = state.nodes[nodeId] ?? state.nodes[String(nodeId)];
  if (!node) return null;

  const verdicts = (state.verdicts || []).filter(
    (v) => String(v.node) === String(nodeId),
  );
  const screen = verdicts.filter((v) => v.rung === "screen");
  const replicate = verdicts.filter((v) => v.rung === "replicate");
  const cascade = state.cascade?.byNode?.[nodeId]
    ?? state.cascade?.byNode?.[String(nodeId)]
    ?? null;

  const loops = verdicts.filter((v) => v.state === "inconclusive").length;
  const isLive = LIVE_STATES.has(node.state) && node.latestVerdict == null;

  const idea = "done"; // node exists

  let freeChecks = "pending";
  if (cascade == null) {
    // Drift vs table "absent→skipped": nodes 3–4 never got verify_level in the
    // golden fixture but still reached tests — treat as done once a test exists.
    freeChecks =
      screen.length > 0 || replicate.length > 0 ? "done" : "skipped";
  } else if (cascade.some((e) => e.passed === false)) {
    freeChecks = "failed";
  } else if (cascade.length > 0 && cascade.every((e) => e.passed === true)) {
    freeChecks = "done";
  } else {
    freeChecks = "pending";
  }

  const build =
    Array.isArray(node.stateHistory) && node.stateHistory.length > 0
      ? "done"
      : "pending";

  let quickTest = "pending";
  if (screen.length > 0) {
    const lastScreen = screen[screen.length - 1];
    quickTest = lastScreen.state === "rejected" ? "failed" : "done";
  }

  let repeatTest = "pending";
  if (replicate.length > 0) {
    repeatTest = "done";
  } else if (quickTest === "failed" || quickTest === "skipped") {
    repeatTest = "skipped";
  } else if (screen.length > 0 && screen[screen.length - 1].state === "rejected") {
    repeatTest = "skipped";
  }

  // After quick declined, later stages skip (not fail).
  if (quickTest === "failed") {
    if (replicate.length === 0) repeatTest = "skipped";
  }

  let hiddenCheck = "pending";
  const hasOracle = verdicts.some(
    (v) => v.oracle_delta != null && Number.isFinite(Number(v.oracle_delta)),
  );
  const hasAttribution = verdicts.some(
    (v) => v.attribution === "clear" || v.attribution === "unclear",
  );
  if (hasOracle || hasAttribution) {
    hiddenCheck = "done";
  } else if (repeatTest === "skipped" || quickTest === "failed") {
    hiddenCheck = "skipped";
  }

  let decisionStatus = "pending";
  let decisionWord = null;
  if (node.latestVerdict?.state != null) {
    decisionStatus = "done";
    decisionWord = stateLabel(node.latestVerdict.state).word;
  } else if (isLive) {
    decisionStatus = "current";
  }

  // If free checks failed before any quick test, skip later GPU stages.
  if (freeChecks === "failed" && screen.length === 0) {
    quickTest = "skipped";
    repeatTest = "skipped";
    hiddenCheck = "skipped";
  }

  const statuses = {
    idea,
    "free-checks": freeChecks,
    build,
    "quick-test": quickTest,
    "repeat-test": repeatTest,
    "hidden-check": hiddenCheck,
    decision: decisionStatus,
  };

  // Live node: mark the first non-done pending stage as current.
  if (isLive) {
    for (const stage of STAGES) {
      if (statuses[stage.id] === "pending") {
        statuses[stage.id] = "current";
        break;
      }
    }
  }

  const stages = STAGES.map((stage) => ({
    id: stage.id,
    label: stage.label,
    status: statuses[stage.id],
  }));

  return {
    stages,
    loops,
    decision: decisionWord,
  };
}

const LEVEL_ORDER = ["omega", "v_sem", "smoke"];

function levelLabel(level) {
  if (level === "omega") return DICT.receiptFree.word;
  if (level === "v_sem") return DICT.checkLlm.word;
  if (level === "smoke") return DICT.receiptSmoke.word;
  return "";
}

function stoppedWord(level) {
  if (level === "omega") return "free";
  if (level === "v_sem") return "reading";
  if (level === "smoke") return "quick run";
  return null;
}

export function buildReceipt(state, contractPayload, nodeId) {
  const rows =
    state?.cascade?.byNode?.[nodeId] ??
    state?.cascade?.byNode?.[String(nodeId)] ??
    null;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const trips = (state.reliability?.ruleTrips || []).filter(
    (t) => String(t.node) === String(nodeId),
  );
  const levels = LEVEL_ORDER.map((level) => {
    const row = rows.find((r) => r.level === level);
    if (!row) return null;
    const ids = Array.isArray(row.trips) ? row.trips : [];
    const tripped = ids.map((id) => {
      const ev = trips.find((t) => t.rule_id === id || t.rule === id);
      return { id, statement: ev?.statement || String(id) };
    });
    return { label: levelLabel(level), passed: row.passed === true, tripped };
  }).filter(Boolean);
  let readings = 0;
  let runs = 0;
  for (const row of rows) {
    readings += Number(row.llm_calls) || 0;
    runs += Number(row.runs) || 0;
  }
  let stoppedAt = null;
  for (const row of rows) {
    if (row.passed === false) {
      stoppedAt = stoppedWord(row.level);
      break;
    }
  }
  let semanticLine = null;
  const rules =
    contractPayload?.available === true && Array.isArray(contractPayload.rules)
      ? contractPayload.rules
      : null;
  if (rules) {
    const n = rules.filter((r) => r.check === "llm").length;
    semanticLine = DICT.receiptSemantic.word.replace("{n}", String(n));
  }
  return {
    levels,
    spend: { readings, runs },
    stoppedAt,
    semanticLine,
  };
}

export function receiptHtml(receipt) {
  if (!receipt) return "";
  const quotes = receipt.levels
    .flatMap((lv) => lv.tripped)
    .map((t) => `<blockquote>${escapeHtml(t.statement)}</blockquote>`)
    .join("");
  const stop =
    receipt.stoppedAt === "free"
      ? `<p>${escapeHtml(DICT.receiptStopFree.word)}</p>`
      : "";
  const spend = `<p class="panel-note">${escapeHtml(String(receipt.spend.readings))} readings · ${escapeHtml(String(receipt.spend.runs))} runs</p>`;
  const semantic = receipt.semanticLine
    ? `<p class="stat-caption">${escapeHtml(receipt.semanticLine)}</p>`
    : "";
  return `${quotes}${stop}${spend}${semantic}`;
}

/** HTML leaf widget for the dossier pipeline strip (D2 exception). */
export function journeyStripHtml(journey, receipt) {
  if (!journey?.stages?.length) return "";
  const chips = journey.stages
    .map((s) => {
      const chip = `<span class="stage stage--${s.status}" data-stage="${s.id}">${escapeHtml(s.label)}</span>`;
      if (s.id === "free-checks" && receipt) {
        return `<details class="stage-receipt"><summary>${chip}</summary>${receiptHtml(receipt)}</details>`;
      }
      return chip;
    })
    .join("");
  const retry =
    journey.loops > 0
      ? `<span class="journey-retry">retry ${journey.loops} of 3</span>`
      : "";
  return `<div class="journey-strip">${chips}${retry}</div>`;
}

