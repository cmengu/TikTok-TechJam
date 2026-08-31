/** V3 Memory page — what the run has learned. Pure fold + HTML. */

import { DICT } from "./copy.js";
import { chipHtml, escapeHtml } from "./chip.js";

const DEFECT_LABEL = {
  crash: "crashed",
  diverged: "diverged",
  timeout: "timed out",
  silently_drops_rows: "dropped rows",
  leak_suspected: "leak suspected",
  no_gain: "no gain",
};

export function bannedRows(state) {
  const forbidden = state?.forbidden && typeof state.forbidden === "object"
    ? state.forbidden
    : {};
  const lessons = Array.isArray(state?.lessons) ? state.lessons : [];
  const rows = [];
  for (const [pattern, ev] of Object.entries(forbidden)) {
    const lesson = lessons.find((l) => l.pattern === pattern) || {};
    const round = lesson.round ?? ev.round ?? ev.first_round ?? null;
    rows.push({
      pattern,
      defect: lesson.defect ?? ev.defect ?? null,
      round,
      node: lesson.node ?? ev.node ?? null,
      seeded: round === 0,
    });
  }
  return rows;
}

export function buildMemory(state, feedbackPayload) {
  if (
    feedbackPayload == null ||
    typeof feedbackPayload !== "object" ||
    feedbackPayload.available !== true
  ) {
    const reason =
      (feedbackPayload && feedbackPayload.reason) || DICT.memoryEmpty.word;
    return {
      weak: [],
      directions: [],
      banned: [],
      verbatim: "",
      empty: true,
      reason,
    };
  }
  const weak = (feedbackPayload.weak || []).map((text) => ({ text: String(text) }));
  const directions = (feedbackPayload.directions || []).map((text) => ({
    text: String(text),
  }));
  const banned = bannedRows(state);
  const verbatim = String(feedbackPayload.text ?? "");
  const empty =
    weak.length === 0 && directions.length === 0 && banned.length === 0;
  return { weak, directions, banned, verbatim, empty, reason: null };
}

function section(title, items, bodyFn) {
  const inner = items.length
    ? items.map(bodyFn).join("")
    : `<p class="empty">${escapeHtml(DICT.memoryEmpty.word)}</p>`;
  return `<section class="card"><h2>${escapeHtml(title)}</h2>${inner}</section>`;
}

export function memoryPageHtml(vm) {
  if (vm.empty && vm.reason) {
    return `<div class="doc"><p class="empty">${escapeHtml(vm.reason)}</p></div>`;
  }
  const weak = section(DICT.memoryWeak.word, vm.weak, (row) =>
    `<p>${escapeHtml(row.text)}</p>`,
  );
  const dirs = section(DICT.memoryDirections.word, vm.directions, (row) =>
    `<p>${escapeHtml(row.text)}</p>`,
  );
  const banned = section(DICT.memoryBanned.word, vm.banned, (row) => {
    const defectWord = DEFECT_LABEL[row.defect] || row.defect || "";
    const seeded = row.seeded
      ? `<p class="stat-caption">${escapeHtml(DICT.memorySeeded.word)}</p>`
      : "";
    const link =
      row.node != null
        ? `<p><a href="#/run/${encodeURIComponent(String(row.node))}">attempt ${escapeHtml(String(row.node))}</a> · round ${escapeHtml(String(row.round ?? "—"))}</p>`
        : `<p>round ${escapeHtml(String(row.round ?? "—"))}</p>`;
    return `<section class="card">
      <p>${escapeHtml(row.pattern)}</p>
      ${defectWord ? chipHtml({ word: defectWord, hint: null }) : ""}
      ${link}
      ${seeded}
    </section>`;
  });
  const verbatim = `<section class="card memory-verbatim">
    <p class="stat-caption">${escapeHtml(DICT.memoryVerbatimLead.word)}</p>
    <pre>${escapeHtml(vm.verbatim)}</pre>
  </section>`;
  return `<div class="doc">
    <h1>${escapeHtml(DICT.memoryTitle.word)}</h1>
    ${weak}${dirs}${banned}${verbatim}
  </div>`;
}
