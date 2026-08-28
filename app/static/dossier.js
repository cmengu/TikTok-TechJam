/** Checkpoint 3: pure node dossier reader (no DOM, no app.js imports). Contract: context/Handoff_app.md, "Task 8". */

import { verdictReading } from "./band.js";

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
