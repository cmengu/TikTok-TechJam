/** F5 monitors view-model tests — node --test, no DOM, no fetch. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildMonitors } from "./monitors.js";

function healthyPayload(overrides = {}) {
  return {
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
    ...overrides,
  };
}

describe("monitors view model", () => {
  it("test_rank_corr_null_renders_n_lt_3", () => {
    const vm = buildMonitors(healthyPayload({ rank_corr: null }));
    const row = vm.numbers.find((n) => n.label === "rank corr");
    assert.equal(row.value, null);
    assert.equal(row.text, "n < 3");
  });

  it("test_rank_corr_zero_renders_zero", () => {
    const vm = buildMonitors(healthyPayload({ rank_corr: 0 }));
    const row = vm.numbers.find((n) => n.label === "rank corr");
    assert.equal(row.value, 0);
    assert.equal(row.text, "0.00");
    assert.notEqual(row.text, "n < 3");
  });

  it("test_gap_alarm_true_is_carried", () => {
    assert.equal(buildMonitors(healthyPayload({ gap_alarm: true })).gap.alarm, true);
    assert.equal(buildMonitors(healthyPayload({ gap_alarm: false })).gap.alarm, false);
  });

  it("test_unavailable_returns_placeholders", () => {
    const vm = buildMonitors({ available: false, reason: "harness.overfit not present" });
    assert.equal(vm.available, false);
    assert.ok(vm.numbers.length > 0);
    for (const row of vm.numbers) {
      assert.equal(row.text, "—");
      assert.notEqual(row.value, 0);
      assert.notEqual(row.text, "0");
    }
    assert.equal(vm.rung.reason, "harness.overfit not present");
  });

  it("test_malformed_payload_returns_null", () => {
    assert.equal(buildMonitors(null), null);
    assert.equal(buildMonitors(undefined), null);
    assert.equal(buildMonitors("nope"), null);
    assert.equal(buildMonitors([]), null);
    assert.equal(buildMonitors({}), null);
    assert.equal(buildMonitors({ available: true }), null);
  });

  it("test_every_number_names_its_source", () => {
    const vm = buildMonitors(healthyPayload());
    assert.ok(vm.numbers.length > 0);
    for (const row of vm.numbers) {
      assert.equal(typeof row.source, "string");
      assert.ok(row.source.startsWith("harness."));
    }
  });

  it("test_seed_consistency_empty_renders_empty", () => {
    const vm = buildMonitors(healthyPayload({ seed_consistency: [] }));
    assert.deepEqual(vm.seedConsistency, []);
    assert.equal(vm.seedEmpty, true);
    assert.ok(!vm.seedConsistency.some((row) => row.value === 0));
  });

  it("test_build_monitors_is_pure", () => {
    const payload = healthyPayload();
    const before = structuredClone(payload);
    const a = buildMonitors(payload);
    const b = buildMonitors(payload);
    assert.deepEqual(a, b);
    assert.deepEqual(payload, before);
  });
});
