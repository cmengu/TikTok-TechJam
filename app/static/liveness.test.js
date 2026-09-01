/** Fix-list item 7 — staleness detection, pure (no DOM, no Date.now). */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BANNED } from "./copy.js";
import { STALL_AFTER_MS, backoffDelay, liveness, stalledText } from "./liveness.js";
import { initial, reduce } from "./reducer.js";

const T0 = Date.parse("2026-08-31T16:14:00.000Z");
const MIN = 60 * 1000;

function run(overrides = {}) {
  return {
    id: "kuairand-20260831-161400",
    startedAt: "2026-08-31T16:14:00.000Z",
    endedAt: null,
    status: "running",
    ...overrides,
  };
}

describe("liveness", () => {
  it("test_fresh_signal_reads_running", () => {
    const v = liveness(run(), T0 + 20 * MIN, T0 + 20 * MIN + 4000);
    assert.equal(v.status, "running");
  });

  it("test_silence_past_threshold_reads_stalled", () => {
    // The real dead-run shape: killed at ~23 min, page open an hour later.
    const lastSignal = T0 + 21 * MIN;
    const now = T0 + 80 * MIN;
    const v = liveness(run(), lastSignal, now);
    assert.equal(v.status, "stalled");
    assert.equal(v.quietMs, now - lastSignal);
  });

  it("test_threshold_is_a_named_constant_near_five_minutes", () => {
    assert.equal(STALL_AFTER_MS, 5 * MIN);
    const v = liveness(run(), T0, T0 + STALL_AFTER_MS - 1);
    assert.equal(v.status, "running");
    const w = liveness(run(), T0, T0 + STALL_AFTER_MS + 1);
    assert.equal(w.status, "stalled");
  });

  it("test_ended_run_is_never_stalled", () => {
    const v = liveness(
      run({ status: "ended", endedAt: "2026-08-31T17:00:00.000Z" }),
      T0,
      T0 + 600 * MIN,
    );
    assert.equal(v.status, "ended");
  });

  it("test_not_started_reads_waiting", () => {
    const v = liveness(run({ startedAt: null, status: "waiting" }), null, T0);
    assert.equal(v.status, "waiting");
  });

  it("test_no_signal_yet_on_a_started_run_falls_back_to_started_at", () => {
    // run_started is itself a signal; a run with zero later events stalls
    // measured from its start, not never.
    const v = liveness(run(), null, T0 + 10 * MIN);
    assert.equal(v.status, "stalled");
  });

  it("test_stalled_text_reports_minutes_and_carries_no_jargon", () => {
    const s = stalledText(44 * MIN + 30 * 1000);
    assert.match(s, /stalled/i);
    assert.match(s, /44m/);
    const re = new RegExp(`\\b(?:${BANNED.join("|")})\\b`, "i");
    assert.equal(re.test(s), false, `banned in: ${s}`);
  });
});

describe("reducer lastSignalAt", () => {
  it("test_events_and_heartbeats_both_advance_last_signal", () => {
    let s = initial();
    s = reduce(s, {
      seq: 1,
      t: "2026-08-31T16:14:00.000Z",
      type: "run_started",
      run: "r",
      protocol_hash: "sha256:x",
    });
    assert.equal(s.lastSignalAt, "2026-08-31T16:14:00.000Z");
    s = reduce(s, {
      seq: 1,
      t: "2026-08-31T16:14:05.000Z",
      type: "heartbeat",
      worker: "trainer",
    });
    assert.equal(s.lastSignalAt, "2026-08-31T16:14:05.000Z");
    s = reduce(s, {
      seq: 2,
      t: "2026-08-31T16:14:03.000Z",
      type: "measurement",
      node: 1,
      metric: "primary",
      value: 0.5,
    });
    // an older-stamped event never rolls the signal clock backwards
    assert.equal(s.lastSignalAt, "2026-08-31T16:14:05.000Z");
  });
});

describe("reconnect backoff", () => {
  it("test_backoff_grows_and_caps", () => {
    assert.equal(backoffDelay(0), 500);
    assert.equal(backoffDelay(1), 1000);
    assert.equal(backoffDelay(2), 2000);
    assert.ok(backoffDelay(10) <= 10000);
    assert.equal(backoffDelay(99), 10000);
  });

  it("test_backoff_never_returns_nonsense", () => {
    for (const n of [-1, null, undefined, NaN]) {
      const d = backoffDelay(n);
      assert.ok(Number.isFinite(d) && d >= 500 && d <= 10000, String(d));
    }
  });
});
