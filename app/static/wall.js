/** V6 wall widget — holdout visit meter. Pure fold + HTML. */

import { DICT } from "./copy.js";
import { escapeHtml } from "./chip.js";

export function buildWall(monitorsPayload) {
  if (
    monitorsPayload == null ||
    typeof monitorsPayload !== "object" ||
    Array.isArray(monitorsPayload) ||
    monitorsPayload.available === false ||
    !("holdout_visits" in monitorsPayload) ||
    !("holdout_cap" in monitorsPayload)
  ) {
    return { available: false };
  }
  const visits = Number(monitorsPayload.holdout_visits) || 0;
  const cap = Number(monitorsPayload.holdout_cap) || 0;
  const pct = cap > 0 ? Math.min(100, Math.round((visits / cap) * 100)) : 0;
  return {
    available: true,
    visits,
    cap,
    pct,
    queries: monitorsPayload.ladder_queries,
    digestsOk: monitorsPayload.digests_ok === true,
    caption: DICT.wallCaption.word,
  };
}

export function wallHtml(wall) {
  if (!wall || wall.available !== true) return "";
  const meter = DICT.wallMeter.word
    .replace("{v}", String(wall.visits))
    .replace("{cap}", String(wall.cap));
  const queries = DICT.wallQueries.word.replace("{q}", String(wall.queries));
  const fingerprints = wall.digestsOk
    ? `<p class="panel-note">${escapeHtml(DICT.wallDigests.word)}</p>`
    : "";
  return `<section class="card wall-widget">
    <p class="wall-meter-label">${escapeHtml(meter)}</p>
    <div class="wall-meter" role="meter" aria-valuenow="${escapeHtml(String(wall.visits))}" aria-valuemin="0" aria-valuemax="${escapeHtml(String(wall.cap))}">
      <div class="wall-meter-fill" style="width:${escapeHtml(String(wall.pct))}%"></div>
    </div>
    <p class="panel-note">${escapeHtml(queries)}</p>
    ${fingerprints}
    <p class="stat-caption">${escapeHtml(wall.caption)}</p>
  </section>`;
}
