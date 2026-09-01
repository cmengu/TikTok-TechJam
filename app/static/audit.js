/** E7 audit view models. Pure: no DOM, no fetch. */

import { DICT, fmtDuration } from "./copy.js";
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
  // Fix list item 12: token rows are structurally 0 for most slices — the
  // researcher only logs when it runs, and training/tuning have no LLM in
  // them at all (training's real spend is gpu_h). Primary rows are the
  // slices that actually spent words; the full four-slice breakdown stays
  // available behind a fold so nothing is hidden.
  const active = slices.filter((s) => (s.tokens_in || 0) + (s.tokens_out || 0) > 0);
  return { slices, active, trainingGpuH: payload.training.gpu_h };
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

// Why a zero row is zero: the researcher just hasn't run; testing and
// tuning never spend words at all.
const SLICE_ZERO_HINTS = {
  researching: "spendStageIdle",
  coding: "spendStageIdle",
  training: "spendStageCompute",
  tuning: "spendStageCompute",
};

export function spendPageHtml(vm) {
  const tiles = vm.active
    .map(
      // The ledger key ({slice}.tokens_in) is for the code, not the viewer —
      // it lives on the hover only (fix list item 10).
      (s) => `<div class="stat" title="${escapeHtml(s.slice)}.tokens_in">
        <span class="stat-value">${escapeHtml(String(s.tokens_in))}</span>
        <span class="stat-caption">${escapeHtml(s.label)}</span>
      </div>`,
    )
    .join("");
  const primary = tiles || `<p class="empty">no spend recorded yet</p>`;
  // Testing's real spend is compute, not words — one plain line, as a
  // duration (0.008 GPU-hours as "0.0" would just look broken again).
  const gpu =
    vm.trainingGpuH > 0
      ? `<p class="spend-gpu" title="training.gpu_h">${escapeHtml(
          DICT.spendGpuLine.word.replace("{t}", fmtDuration(vm.trainingGpuH * 3600)),
        )}</p>`
      : "";
  const foldRows = vm.slices
    .map((s) => {
      const zero = (s.tokens_in || 0) + (s.tokens_out || 0) <= 0;
      const note = zero
        ? ` <span class="panel-note">${escapeHtml(DICT[SLICE_ZERO_HINTS[s.slice]].word)}</span>`
        : "";
      return `<li>${escapeHtml(s.label)} — ${escapeHtml(String(s.tokens_in))} words in · ${escapeHtml(String(s.tokens_out))} words out${note}</li>`;
    })
    .join("");
  const fold = `<details class="spend-fold">
    <summary>${escapeHtml(DICT.spendFoldSummary.word)}</summary>
    <ul>${foldRows}</ul>
  </details>`;
  return `<div class="doc">${primary}${gpu}${fold}</div>`;
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
