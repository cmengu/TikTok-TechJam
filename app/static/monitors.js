/** F5 monitors view model. Pure: no DOM, no fetch, no HTML. */

import { claimReasonLabel } from "./copy.js";

const CONTRACT_KEYS = [
  "available",
  "primary",
  "spread",
  "oracle_gap",
  "gap_alarm",
  "seed_consistency",
  "rank_corr",
  "ladder_queries",
  "claim_level",
  "claim_reason",
];

const NUMBER_SPECS = [
  {
    label: "primary",
    key: "primary",
    source: "harness.overfit.headline",
    digits: 4,
  },
  {
    label: "spread",
    key: "spread",
    source: "harness.overfit.headline",
    digits: 4,
  },
  {
    label: "rank corr",
    key: "rank_corr",
    source: "harness.overfit.split_rank_corr",
    digits: 2,
    nullText: "n < 3",
  },
  {
    label: "ladder queries",
    key: "ladder_queries",
    source: "harness.overfit.ladder_queries",
    asInt: true,
  },
];

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function dashRow(spec) {
  return {
    label: spec.label,
    value: null,
    text: "—",
    source: spec.source,
  };
}

function numberRow(spec, payload) {
  const value = payload[spec.key];
  if (spec.nullText && (value === null || value === undefined)) {
    return {
      label: spec.label,
      value: null,
      text: spec.nullText,
      source: spec.source,
    };
  }
  if (spec.asInt) {
    return {
      label: spec.label,
      value,
      text: String(value),
      source: spec.source,
    };
  }
  return {
    label: spec.label,
    value,
    text: Number(value).toFixed(spec.digits),
    source: spec.source,
  };
}

function asPairs(rows, valueKey) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    if (Array.isArray(row)) {
      return { node: row[0], [valueKey]: row[1] };
    }
    return { node: row.node, [valueKey]: row[valueKey] ?? row.gap ?? row.value };
  });
}

function placeholders(reason) {
  return {
    available: false,
    numbers: NUMBER_SPECS.map(dashRow),
    gap: { alarm: false, points: [] },
    seedConsistency: [],
    seedEmpty: true,
    rung: { level: "—", reason: reason || "—" },
  };
}

export function buildMonitors(payload) {
  if (!isPlainObject(payload) || !("available" in payload)) return null;
  if (payload.available === false) {
    return placeholders(payload.reason);
  }
  for (const key of CONTRACT_KEYS) {
    if (!(key in payload)) return null;
  }
  const seedConsistency = asPairs(payload.seed_consistency, "value").map((row) => ({
    node: row.node,
    value: row.value,
    text: Number(row.value).toFixed(2),
  }));
  return {
    available: true,
    numbers: NUMBER_SPECS.map((spec) => numberRow(spec, payload)),
    gap: {
      alarm: Boolean(payload.gap_alarm),
      points: asPairs(payload.oracle_gap, "gap"),
    },
    seedConsistency,
    seedEmpty: seedConsistency.length === 0,
    rung: {
      level: payload.claim_level,
      reason: claimReasonLabel(payload.claim_reason),
    },
  };
}
