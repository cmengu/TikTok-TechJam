/** V1 Rulebook page — pure fold + HTML. No DOM, no fetch. */

import { DICT } from "./copy.js";
import { chipHtml, escapeHtml } from "./chip.js";

function checkLabel(check) {
  if (check === "static") return DICT.checkStatic.word;
  if (check === "llm") return DICT.checkLlm.word;
  return "";
}

export function buildRulebook(contractPayload, state) {
  if (
    contractPayload == null ||
    typeof contractPayload !== "object" ||
    Array.isArray(contractPayload) ||
    contractPayload.available !== true ||
    !Array.isArray(contractPayload.rules)
  ) {
    const reason =
      (contractPayload &&
        typeof contractPayload === "object" &&
        typeof contractPayload.reason === "string" &&
        contractPayload.reason) ||
      DICT.rulebookUnavailable.word;
    return { available: false, reason };
  }
  const trips = state?.reliability?.ruleTripsByRule || {};
  const cards = contractPayload.rules.map((rule) => ({
    id: rule.id,
    statement: rule.statement,
    checkLabel: checkLabel(rule.check),
    severity: rule.severity,
    trips: Number(trips[rule.id]) || 0,
  }));
  return { available: true, cards };
}

export function rulebookPageHtml(vm) {
  if (!vm || vm.available !== true) {
    const reason = vm?.reason || DICT.rulebookUnavailable.word;
    return `<div class="doc"><p class="empty">${escapeHtml(reason)}</p></div>`;
  }
  const header = DICT.rulebookHeader.word.replace("{n}", String(vm.cards.length));
  const cards = vm.cards
    .map((card) => {
      const chips = [
        chipHtml({ word: card.checkLabel, hint: null }),
        chipHtml({ word: card.severity, hint: null }),
        `<span class="stat-caption">trips ${escapeHtml(String(card.trips))}</span>`,
      ].join(" ");
      return `<section class="card rulebook-card">
      <p class="rulebook-statement">${escapeHtml(card.statement)}</p>
      <p class="rulebook-chips">${chips}</p>
    </section>`;
    })
    .join("");
  return `<div class="doc">
    <p class="stat-caption">${escapeHtml(header)}</p>
    ${cards}
  </div>`;
}
