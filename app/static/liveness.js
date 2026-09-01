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

// --- Fix-list item 8: reconnect schedule for the event streams. A tab
// opened before the run directory exists gets a 404 and must keep trying —
// but not hammer the server at a fixed 500ms forever. Exponential from
// 500ms, capped at 10s; callers reset the attempt count on any message. ---

export const BACKOFF_BASE_MS = 500;
export const BACKOFF_CAP_MS = 10 * 1000;

export function backoffDelay(attempt) {
  const n = Number.isFinite(attempt) && attempt > 0 ? attempt : 0;
  return Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** Math.min(n, 30));
}

// --- Fix-list item 9: run-picker entry labels. Uses the same staleness
// signal as the header: a run with no run_ended event and a quiet log is
// "stalled", not "live". The /runs endpoint supplies started, last_signal
// and ended per run. ---

export function runPickerLabel(row, nowMs) {
  if (row == null || typeof row !== "object") return "?";
  const id = row.run_id ?? "?";
  const startedMs = toMs(row.started);
  const started =
    startedMs != null
      ? new Date(startedMs).toLocaleString(undefined, {
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
      : "?";
  let word = "live";
  if (row.ended) word = "ended";
  else {
    const signalMs = toMs(row.last_signal) ?? startedMs;
    if (signalMs == null || nowMs - signalMs > STALL_AFTER_MS) word = "stalled";
  }
  return `${id} · started ${started} · ${word}`;
}
