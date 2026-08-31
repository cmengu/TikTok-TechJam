/** E6 Ideas view model. Pure: no DOM, no fetch. */

import { ideaOutcome } from "./reducer.js";
import { fmtDelta } from "./copy.js";

function tokensFor(ev) {
  const inn = Number(ev?.tokens_in) || 0;
  const out = Number(ev?.tokens_out) || 0;
  return inn + out;
}

function card(ev, extra) {
  return {
    id: ev.id,
    pattern: ev.pattern ?? ev.mechanism ?? null,
    stage: ev.stage ?? null,
    citation: ev.citation ?? null,
    tokens: tokensFor(ev),
    expectedGain: ev.expected_gain ?? null,
    ...extra,
  };
}

/**
 * buildIdeas(state) → { inPlay, done, banned } | null
 * Each queued idea appears on exactly one shelf.
 */
export function buildIdeas(state) {
  if (!state?.ideas?.order || !state.ideas.byId) return null;
  const forbidden = state.forbidden && typeof state.forbidden === "object"
    ? state.forbidden
    : {};
  const lessons = Array.isArray(state.lessons) ? state.lessons : [];
  const inPlay = [];
  const done = [];
  const banned = [];
  for (const id of state.ideas.order) {
    const ev = state.ideas.byId[id];
    if (!ev) continue;
    const pattern = ev.pattern ?? ev.mechanism;
    const ban = pattern != null ? forbidden[pattern] : null;
    if (ban) {
      const note = lessons.find((l) => l.pattern === pattern) ?? null;
      banned.push(
        card(ev, {
          reason: ban.reason ?? null,
          note: note?.summary ?? note?.defect ?? null,
        }),
      );
      continue;
    }
    const verdict = ideaOutcome(state, id);
    if (verdict) {
      done.push(
        card(ev, {
          outcome: verdict.state ?? null,
          actualDelta: verdict.delta_mean ?? null,
        }),
      );
    } else {
      inPlay.push(card(ev, {}));
    }
  }
  return { inPlay, done, banned };
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function shelfHtml(title, cards, bodyFn) {
  const inner = cards.length
    ? cards.map((c) => `<section class="card">${bodyFn(c)}</section>`).join("")
    : `<p class="empty">none</p>`;
  return `<h2>${escapeHtml(title)}</h2>${inner}`;
}

export function ideasPageHtml(vm) {
  const play = shelfHtml("In play", vm.inPlay, (c) => {
    const gain = c.expectedGain == null ? "—" : String(c.expectedGain);
    return `<h3>${escapeHtml(c.pattern || c.id)}</h3>
      <p class="stat-caption">${escapeHtml(c.stage || "")}</p>
      <p>expected ${escapeHtml(gain)}</p>`;
  });
  const done = shelfHtml("Done", vm.done, (c) => {
    const expected = c.expectedGain == null ? "—" : String(c.expectedGain);
    return `<h3>${escapeHtml(c.pattern || c.id)}</h3>
      <p class="stat-caption">${escapeHtml(c.outcome || "")}</p>
      <p>expected ${escapeHtml(expected)} · actual ${escapeHtml(fmtDelta(c.actualDelta))}</p>`;
  });
  const banned = shelfHtml("Banned", vm.banned, (c) => {
    return `<h3>${escapeHtml(c.pattern || c.id)}</h3>
      <p>${escapeHtml(c.reason || "")}</p>
      ${c.note ? `<p class="stat-caption">${escapeHtml(c.note)}</p>` : ""}`;
  });
  return `<div class="doc">${play}${done}${banned}</div>`;
}
