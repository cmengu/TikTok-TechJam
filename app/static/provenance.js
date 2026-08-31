/** V4 provenance stamps. Pure classifier + HTML leaf widget.
 * MEASURED mirrors harness/events.py (the source of truth). */

import { DICT } from "./copy.js";
import { escapeHtml, escapeAttr } from "./chip.js";

/** @see harness/events.py MEASURED */
export const MEASURED = new Set([
  "delta_mean",
  "delta_per_seed",
  "band",
  "score",
  "gauc",
  "ndcg_at_5",
  "primary",
  "holdout_score",
  "oracle_score",
  "oracle_delta",
  "value",
  "best_reported",
  "scores",
]);

export function stampFor(ev) {
  if (ev == null || typeof ev !== "object") return null;
  const keys = Object.keys(ev);
  const hasMeasured = keys.some((k) => MEASURED.has(k));
  if (hasMeasured && ev.producer === "measure") return "measured";
  const hasForecast = keys.some((k) => String(k).startsWith("expected_"));
  if (hasForecast && ev.type === "hypothesis_queued") return "forecast";
  return null;
}

export function stampHtml(kind) {
  if (kind !== "measured" && kind !== "forecast") return "";
  const word =
    kind === "measured" ? DICT.stampMeasured.word : DICT.stampForecast.word;
  return `<span class="stamp stamp--${kind}" title="${escapeAttr(DICT.stampHover.word)}">${escapeHtml(word)}</span>`;
}

export function provenanceTileHtml(counts) {
  const n = counts?.measured ?? 0;
  const m = counts?.forecasts ?? 0;
  const line = DICT.provenanceTile.word
    .replace("{n}", String(n))
    .replace("{m}", String(m));
  return `<div class="provenance-tile">
    <p>${escapeHtml(line)}</p>
    <p class="stat-caption">${escapeHtml(DICT.provenanceCaption.word)}</p>
  </div>`;
}
