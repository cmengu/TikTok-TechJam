/** Fix-list item 7 — is the run actually alive? Pure: callers pass nowMs.
 *
 * A killed harness (kill -9, crash, sleeping laptop) writes no run_ended
 * event, so run.status stays "running" forever and the elapsed clock ticks
 * client-side. The honest signal is silence: no event and no heartbeat for
 * longer than any normal gap between signals. Real runs heartbeat every few
 * seconds and event at least every few minutes (a full replicate is ~6 min),
 * so five minutes of total silence means nobody is home.
 */

import { DICT } from "./copy.js";

export const STALL_AFTER_MS = 5 * 60 * 1000;

/**
 * @param {{startedAt: ?string, status: string}} run reduced run slice
 * @param {?string|number} lastSignalAt newest t across events + heartbeats
 * @param {number} nowMs wall clock (the view owns the clock, not the reducer)
 * @returns {{status: "waiting"|"running"|"stalled"|"ended", quietMs: number}}
 */
export function liveness(run, lastSignalAt, nowMs) {
  if (run.status === "ended") return { status: "ended", quietMs: 0 };
  if (!run.startedAt || run.status === "waiting") {
    return { status: "waiting", quietMs: 0 };
  }
  // run_started is itself a signal: a run with no later events still stalls,
  // measured from its start rather than never.
  const signalMs = toMs(lastSignalAt) ?? toMs(run.startedAt);
  if (signalMs == null) return { status: "running", quietMs: 0 };
  const quietMs = Math.max(0, nowMs - signalMs);
  if (quietMs > STALL_AFTER_MS) return { status: "stalled", quietMs };
  return { status: "running", quietMs };
}

export function stalledText(quietMs) {
  const minutes = Math.max(1, Math.floor(quietMs / 60000));
  return DICT.runStalled.word.replace("{m}", String(minutes));
}

function toMs(t) {
  if (t == null) return null;
  const ms = typeof t === "number" ? t : Date.parse(t);
  return Number.isFinite(ms) ? ms : null;
}
