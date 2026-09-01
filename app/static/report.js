/** E8 Summary view model. Pure: no DOM, no fetch. */

import { DICT, claimLabel, fmtScore } from "./copy.js";
import { renderMarkdown } from "./brief.js";
import { escapeHtml } from "./chip.js";

export function buildReport(payload) {
  if (payload == null || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  if (payload.available !== true) return null;
  if (typeof payload.markdown !== "string") return null;
  return { markdown: payload.markdown };
}

export function buildReportHero(monitors) {
  if (
    monitors == null ||
    typeof monitors !== "object" ||
    Array.isArray(monitors) ||
    monitors.available !== true
  ) {
    return { score: "—", trustWord: "—", trustHint: null };
  }
  const trust = claimLabel(monitors.claim_level);
  return {
    score: fmtScore(monitors.primary),
    trustWord: trust.word,
    trustHint: trust.hint ?? null,
  };
}


export function reportPageHtml(report, hero) {
  const hint =
    hero.trustHint != null && hero.trustHint !== ""
      ? ` data-hint="${escapeHtml(hero.trustHint).replaceAll('"', "&quot;")}"`
      : "";
  const body = report
    ? renderMarkdown(report.markdown)
    : `<p class="empty">the run has not finished — the summary writes itself at the end</p>`;
  return `<div class="doc">
    <div class="stat">
      <span class="stat-value">${escapeHtml(hero.score)}</span>
      <span class="stat-caption"${hint}>${escapeHtml(hero.trustWord)}</span>
      <span class="stat-src" title="monitors.primary">${escapeHtml(DICT.scoreSource.word)}</span>
    </div>
    ${body}
  </div>`;
}
