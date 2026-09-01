/** F2 dashboard strip + hero view models, plus the hero's HTML leaf.
 * Pure: no DOM, no fetch. */

import { DICT, claimLabel, claimReasonLabel, fmtScore, heroEmptyLabel } from "./copy.js";
import { escapeHtml, escapeAttr } from "./chip.js";
import { stampHtml } from "./provenance.js";

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function dashIfNull(value) {
  return value == null ? "—" : value;
}

export function buildRung(monitorsPayload) {
  if (!isPlainObject(monitorsPayload) || monitorsPayload.available !== true) {
    return { level: "—", reason: "—" };
  }
  return {
    level: monitorsPayload.claim_level,
    reason: claimReasonLabel(monitorsPayload.claim_reason),
  };
}

export function buildLastMove(state) {
  if (!isPlainObject(state) || !Array.isArray(state.moves) || state.moves.length === 0) {
    return null;
  }
  const ev = state.moves[state.moves.length - 1];
  return {
    round: ev.round,
    kind: dashIfNull(ev.kind),
    parent: dashIfNull(ev.parent),
    reason: ev.reason,
  };
}

export function buildCascadeCounter(state) {
  const empty = {
    rejected: { omega: 0, v_sem: 0, smoke: 0 },
    llmCalls: 0,
    runs: 0,
  };
  if (!isPlainObject(state) || !isPlainObject(state.cascade)) return empty;
  const rejected = state.cascade.rejected || {};
  const counters = state.cascade.counters || {};
  return {
    rejected: {
      omega: rejected.omega ?? 0,
      v_sem: rejected.v_sem ?? 0,
      smoke: rejected.smoke ?? 0,
    },
    llmCalls: counters.llmCalls ?? 0,
    runs: counters.runs ?? 0,
  };
}

const FUNNEL = [
  { key: "papersRead", label: "papers", href: "#/research" },
  { key: "ideasProposed", label: "ideas", href: "#/hypotheses" },
  { key: "attemptsBuilt", label: "attempts", href: "#/run" },
  { key: "accepted", label: "accepted", href: "#/run" },
];

function funnelFrom(trace) {
  const t = trace && typeof trace === "object" ? trace : {};
  return FUNNEL.map((step) => ({
    label: step.label,
    href: step.href,
    count: typeof t[step.key] === "number" ? t[step.key] : 0,
  }));
}

/**
 * buildHero(monitorsPayload, trace) → { score, trust:{word,hint}, caption, funnel }
 * caption is payload.claim_reason through claimReasonLabel (the harness
 * writes it in its own vocabulary). Unavailable score is "—", never "0.0000".
 */
export function buildHero(monitorsPayload, trace, live = null) {
  const funnel = funnelFrom(trace);
  const available =
    isPlainObject(monitorsPayload) && monitorsPayload.available === true;
  const score = available ? fmtScore(monitorsPayload.primary) : "—";
  // No score (monitors missing, or available with a null primary) → the
  // whole trust/caption/source apparatus would be describing a number that
  // doesn't exist. Collapse it to one sentence; heroHtml renders the quiet
  // variant off hero.empty.
  if (score === "—") {
    return {
      score: "—",
      trust: { word: "—", hint: null },
      caption: "",
      empty: heroEmptyLabel(live),
      funnel,
    };
  }
  const trust = claimLabel(monitorsPayload.claim_level);
  return {
    score,
    trust: { word: trust.word, hint: trust.hint ?? null },
    caption: claimReasonLabel(monitorsPayload.claim_reason),
    empty: null,
    funnel,
  };
}

export function provenanceCounts(state) {
  const p = state?.provenance || {};
  return { measured: p.measured || 0, forecasts: p.forecasts || 0 };
}

// The hero's HTML leaf. The "measured" stamp is provenance for a number that
// exists — before the first measurement the score is "\u2014" and a stamp
// glued to a dash would claim provenance for nothing, so no value means no
// stamp (fix list item 2).
export function heroHtml(hero) {
  const funnel = hero.funnel
    .map(
      (s) =>
        `<a class="funnel-step" href="${escapeAttr(s.href)}"><span class="funnel-count">${escapeHtml(String(s.count))}</span> ${escapeHtml(s.label)}</a>`,
    )
    .join('<span class="funnel-arrow">\u2192</span>');
  // No value \u2192 no stamp, no source label, no trust chip. Same principle as
  // the stamp fix above: provenance and trust glued to a dash would claim
  // things about a number that doesn't exist. One sentence instead.
  if (hero.empty != null) {
    return `
    <div class="stat">
      <span class="stat-value dashboard-hero-score dashboard-hero-score--empty">${escapeHtml(hero.score)}</span>
    </div>
    <p class="dashboard-hero-caption">${escapeHtml(hero.empty)}</p>
    <div class="funnel">${funnel}</div>
  `;
  }
  const hint =
    hero.trust.hint != null && hero.trust.hint !== ""
      ? ` data-hint="${escapeAttr(hero.trust.hint)}"`
      : "";
  return `
    <div class="stat">
      <span class="stat-value dashboard-hero-score">${escapeHtml(hero.score)}</span>${stampHtml("measured")}
      <span class="chip-state"${hint}>${escapeHtml(hero.trust.word)}</span>
      <span class="stat-src" title="monitors.primary">${escapeHtml(DICT.scoreSource.word)}</span>
    </div>
    <p class="dashboard-hero-caption">${escapeHtml(hero.caption)}</p>
    <div class="funnel">${funnel}</div>
  `;
}
