/** F2 dashboard strip view models. Pure: no DOM, no fetch, no HTML. */

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
