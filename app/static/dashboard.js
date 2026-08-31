/** F2 dashboard strip + hero view models. Pure: no DOM, no fetch, no HTML. */

import { claimLabel, fmtScore } from "./copy.js";

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function dashIfNull(value) {
  return value == null ? "—" : value;
}

export function buildRung(monitorsPayload) {
  if (!isPlainObject(monitorsPayload) || monitorsPayload.available !== true) {
    return { level: "—", reason: "—" };
  }
  return {
    level: monitorsPayload.claim_level,
    reason: monitorsPayload.claim_reason,
  };
}

export function buildLastMove(state) {
  if (!isPlainObject(state) || !Array.isArray(state.moves) || state.moves.length === 0) {
    return null;
  }
  const ev = state.moves[state.moves.length - 1];
  return {
    round: ev.round,
    kind: dashIfNull(ev.kind),
    parent: dashIfNull(ev.parent),
    reason: ev.reason,
  };
}

export function buildCascadeCounter(state) {
  const empty = {
    rejected: { omega: 0, v_sem: 0, smoke: 0 },
    llmCalls: 0,
    runs: 0,
  };
  if (!isPlainObject(state) || !isPlainObject(state.cascade)) return empty;
  const rejected = state.cascade.rejected || {};
  const counters = state.cascade.counters || {};
  return {
    rejected: {
      omega: rejected.omega ?? 0,
      v_sem: rejected.v_sem ?? 0,
      smoke: rejected.smoke ?? 0,
    },
    llmCalls: counters.llmCalls ?? 0,
    runs: counters.runs ?? 0,
  };
}

const FUNNEL = [
  { key: "papersRead", label: "papers", href: "#/research" },
  { key: "ideasProposed", label: "ideas", href: "#/hypotheses" },
  { key: "attemptsBuilt", label: "attempts", href: "#/run" },
  { key: "accepted", label: "accepted", href: "#/run" },
];

function funnelFrom(trace) {
  const t = trace && typeof trace === "object" ? trace : {};
  return FUNNEL.map((step) => ({
    label: step.label,
    href: step.href,
    count: typeof t[step.key] === "number" ? t[step.key] : 0,
  }));
}

/**
 * buildHero(monitorsPayload, trace) → { score, trust:{word,hint}, caption, funnel }
 * caption is payload.claim_reason byte-for-byte. Unavailable score is "—", never "0.0000".
 */
export function buildHero(monitorsPayload, trace) {
  const funnel = funnelFrom(trace);
  if (!isPlainObject(monitorsPayload) || monitorsPayload.available !== true) {
    return {
      score: "—",
      trust: { word: "—", hint: null },
      caption: "",
      funnel,
    };
  }
  const trust = claimLabel(monitorsPayload.claim_level);
  return {
    score: fmtScore(monitorsPayload.primary),
    trust: { word: trust.word, hint: trust.hint ?? null },
    caption: monitorsPayload.claim_reason == null ? "" : String(monitorsPayload.claim_reason),
    funnel,
  };
}

export function provenanceCounts(state) {
  const p = state?.provenance || {};
  return { measured: p.measured || 0, forecasts: p.forecasts || 0 };
}
