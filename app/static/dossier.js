/** Checkpoint 3: pure node dossier reader (no DOM, no app.js imports). Contract: context/Handoff_app.md, "Task 8". */

import { verdictReading } from "./band.js";
import { sentence } from "./feed.js";
import { levelLabel } from "./copy.js";

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function isFiniteNumber(x) {
  return typeof x === "number" && Number.isFinite(x);
}

// buildDossier(state, nodeId) -> { node, verdicts } | null.
//
// node is state.nodes[nodeId] verbatim: { id, parent, kind, hypothesisId,
// state, stateHistory, scores, seeds, bands, latestVerdict, failures,
// recoveries, ruleTrips, createdSeq } (reducer.js:177-195). Its own
// failures/recoveries/ruleTrips arrays are already scoped to this node by
// the reducer (reducer.js's failure/recovery/rule_trip cases append onto
// state.nodes[ev.node]'s own arrays), so nothing here re-filters them.
//
// verdicts is state.verdicts filtered to this node by ev.node, newest first
// by seq, each paired with band.js's own reading of it — band.js is the
// only module that interprets a band, so this one only calls verdictReading
// and never re-derives what it does.
//
// Node ids arrive as numbers from node_created but reach this module as
// strings from the URL (app.js's selectedRunNodeId) — ev.node is compared
// with String() on both sides, the same way tree.js's hasNode and
// app.js's renderTreeNode already do. The state.nodes[nodeId] lookup itself
// needs no such conversion: JS object keys are always strings, so bracket
// access already coerces a numeric id.
//
// Pure and total: never throws on any input, returns null for an unknown id
// or an unusable state.
export function buildDossier(state, nodeId) {
  try {
    if (!isPlainObject(state)) return null;
    if (nodeId === null || nodeId === undefined) return null;
    const nodes = state.nodes;
    if (!isPlainObject(nodes)) return null;
    if (
      !Object.prototype.hasOwnProperty.call(nodes, nodeId) ||
      !isPlainObject(nodes[nodeId])
    ) {
      return null;
    }
    const node = nodes[nodeId];

    const idStr = String(nodeId);
    const verdictsRaw = Array.isArray(state.verdicts) ? state.verdicts : [];
    const verdicts = verdictsRaw
      .filter((ev) => isPlainObject(ev) && String(ev.node) === idStr)
      .map((verdict) => ({ verdict, reading: verdictReading(verdict) }));

    verdicts.sort((a, b) => {
      const aSeq = isFiniteNumber(a.verdict.seq) ? a.verdict.seq : -Infinity;
      const bSeq = isFiniteNumber(b.verdict.seq) ? b.verdict.seq : -Infinity;
      return bSeq - aSeq; // newest first
    });

    return { node, verdicts };
  } catch (_) {
    return null;
  }
}

function meanScores(scores) {
  if (!Array.isArray(scores) || !scores.length) return null;
  const nums = scores.filter(isFiniteNumber);
  if (!nums.length) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

/**
 * End-to-end attempt trail. Rows with no data are omitted.
 * Order: paper → idea → free checks → each test → hidden check → decision → note.
 */
export function buildAttemptTrail(state, nodeId) {
  if (!isPlainObject(state) || nodeId == null) return [];
  const node = state.nodes?.[nodeId] ?? state.nodes?.[String(nodeId)];
  if (!isPlainObject(node)) return [];
  const idStr = String(node.id ?? nodeId);
  const rows = [];

  const sources = Array.isArray(state.research?.sources)
    ? state.research.sources
    : [];
  const paper = sources.find((s) => s && String(s.node) === idStr);
  if (paper) {
    rows.push({
      kind: "paper",
      title: paper.title ?? "",
      href: "#/research",
    });
  }

  const ideaId = node.hypothesisId;
  const idea = ideaId != null ? state.ideas?.byId?.[ideaId] : null;
  if (idea) {
    rows.push({
      kind: "idea",
      pattern: idea.pattern ?? idea.mechanism ?? null,
      expectedGain: idea.expected_gain ?? null,
    });
  }

  const cascade =
    state.cascade?.byNode?.[node.id] ??
    state.cascade?.byNode?.[idStr] ??
    [];
  const passed = Array.isArray(cascade)
    ? cascade.filter((e) => e && e.passed === true)
    : [];
  if (passed.length) {
    rows.push({
      kind: "free-checks",
      levels: passed.map((e) => levelLabel(e.level).word),
    });
  }

  const verdicts = (Array.isArray(state.verdicts) ? state.verdicts : [])
    .filter((v) => isPlainObject(v) && String(v.node) === idStr)
    .slice()
    .sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
  for (const v of verdicts) {
    if (v.rung === "screen") {
      rows.push({
        kind: "quick-test",
        score: meanScores(v.scores),
        band: Array.isArray(v.band) ? v.band : null,
      });
    } else if (v.rung === "replicate") {
      rows.push({
        kind: "repeat-test",
        score: meanScores(v.scores),
        band: Array.isArray(v.band) ? v.band : null,
      });
    }
  }

  const measurements = Array.isArray(state.measurements)
    ? state.measurements
    : [];
  for (const m of measurements) {
    if (!isPlainObject(m) || String(m.node) !== idStr) continue;
    if (m.rung === "holdout" || m.rung === "oracle") {
      rows.push({
        kind: "hidden-check",
        score: isFiniteNumber(m.value) ? m.value : null,
      });
    }
  }

  if (node.latestVerdict) {
    rows.push({
      kind: "decision",
      text: sentence(node.latestVerdict),
    });
  }

  const lessons = Array.isArray(state.lessons) ? state.lessons : [];
  for (const lesson of lessons) {
    if (lesson && String(lesson.node) === idStr) {
      rows.push({
        kind: "note",
        text: lesson.summary ?? "",
      });
    }
  }
  return rows;
}
