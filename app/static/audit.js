/** E7 audit view models. Pure: no DOM, no fetch. */

import { fmtDuration } from "./copy.js";
import { escapeHtml } from "./chip.js";

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function pairVerdict(delta) {
  if (delta == null || typeof delta !== "number" || Number.isNaN(delta)) return null;
  return delta < 0 ? "shrank" : "held up";
}

/*
 * GET /runs/{id}/audit/replication payload shape (tree is authority):
 * [{ node, screen_vs_full, one_vs_many_seeds, searchval_vs_holdout }, ...]
 */
export function buildDoubleChecks(payload) {
  if (!Array.isArray(payload)) return null;
  const rows = [];
  for (const row of payload) {
    if (!isPlainObject(row) || row.node == null) return null;
    rows.push({
      node: row.node,
      quickVsRepeat: row.screen_vs_full,
      quickVsRepeatVerdict: pairVerdict(row.screen_vs_full),
      oneVsMany: row.one_vs_many_seeds,
      oneVsManyVerdict: pairVerdict(row.one_vs_many_seeds),
      repeatVsHidden: row.searchval_vs_holdout,
      repeatVsHiddenVerdict: pairVerdict(row.searchval_vs_holdout),
    });
  }
  return { rows };
}

const SLICE_LABELS = {
  researching: "reading papers",
  coding: "writing code",
  training: "testing",
  tuning: "tuning",
};
const SLICE_ORDER = ["researching", "coding", "training", "tuning"];

/*
 * GET /runs/{id}/audit/cost payload shape (tree is authority):
 * { researching|coding|training|tuning: { tokens_in, tokens_out, gpu_h } }
 */
export function buildSpend(payload) {
  if (!isPlainObject(payload)) return null;
  const slices = [];
  for (const key of SLICE_ORDER) {
    const row = payload[key];
    if (!isPlainObject(row)) return null;
    if (!("tokens_in" in row) || !("tokens_out" in row) || !("gpu_h" in row)) {
      return null;
    }
    slices.push({
      slice: key,
      label: SLICE_LABELS[key],
      tokens_in: row.tokens_in,
      tokens_out: row.tokens_out,
      gpu_h: row.gpu_h,
    });
  }
  return { slices };
}

/*
 * GET /runs/{id}/audit/reliability payload shape (tree is authority):
 * { failures_by_class, recoveries: {ok, failed},
 *   time_to_first_valid_submission_s, longest_unattended_s, rule_trips }
 */
export function buildStability(payload) {
  if (!isPlainObject(payload)) return null;
  if (!isPlainObject(payload.failures_by_class)) return null;
  if (!isPlainObject(payload.recoveries)) return null;
  if (typeof payload.rule_trips !== "number") return null;
  if (typeof payload.longest_unattended_s !== "number") return null;
  const crashes = Object.entries(payload.failures_by_class).map(([kind, count]) => ({
    kind,
    count,
  }));
  return {
    crashes,
    rescued: payload.recoveries.ok,
    rulebookTrips: payload.rule_trips,
    longestUnattendedS: payload.longest_unattended_s,
    longestUnattended: fmtDuration(payload.longest_unattended_s),
  };
}


export function doubleChecksPageHtml(vm) {
  const rows = vm.rows
    .map((r) => {
      const cell = (delta, verdict) =>
        verdict
          ? `${escapeHtml(String(delta))} · ${escapeHtml(verdict)}`
          : "—";
      return `<tr>
        <td>#${escapeHtml(String(r.node))}</td>
        <td>${cell(r.quickVsRepeat, r.quickVsRepeatVerdict)}</td>
        <td>${cell(r.oneVsMany, r.oneVsManyVerdict)}</td>
        <td>${cell(r.repeatVsHidden, r.repeatVsHiddenVerdict)}</td>
      </tr>`;
    })
    .join("");
  return `<div class="doc">
    <table>
      <thead><tr><th>attempt</th><th>quick vs repeat</th><th>one vs many</th><th>repeat vs hidden</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

export function spendPageHtml(vm) {
  const tiles = vm.slices
    .map(
      (s) => `<div class="stat">
        <span class="stat-value">${escapeHtml(String(s.tokens_in))}</span>
        <span class="stat-caption">${escapeHtml(s.label)}</span>
        <span class="stat-src">${escapeHtml(s.slice)}.tokens_in</span>
      </div>`,
    )
    .join("");
  return `<div class="doc">${tiles}</div>`;
}

export function stabilityPageHtml(vm) {
  const crashes = vm.crashes.length
    ? `<ul>${vm.crashes
        .map(
          (c) =>
            `<li>${escapeHtml(c.kind)} × ${escapeHtml(String(c.count))}</li>`,
        )
        .join("")}</ul>`
    : `<p class="empty">no crashes</p>`;
  return `<div class="doc">
    <section class="card">
      <h2>Crashes</h2>
      ${crashes}
      <p>rescued ${escapeHtml(String(vm.rescued))}</p>
      <p>rulebook trips ${escapeHtml(String(vm.rulebookTrips))}</p>
      <p>longest unattended ${escapeHtml(vm.longestUnattended)}</p>
    </section>
  </div>`;
}
