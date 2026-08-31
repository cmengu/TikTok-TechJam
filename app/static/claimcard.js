/** V5 claim card — why we believe an attempt. Pure fold + HTML. */

import { DICT } from "./copy.js";
import { escapeHtml } from "./chip.js";

function mustMove(direction) {
  if (direction === "positive" || direction === "up") return DICT.claimMustUp.word;
  if (direction === "negative" || direction === "down") return DICT.claimMustDown.word;
  return "";
}

function movedWord(moved) {
  if (moved === true) return DICT.claimMovedYes.word;
  if (moved === false) return DICT.claimMovedNo.word;
  return DICT.claimNotMeasured.word;
}

export function buildClaimCard(state, nodeId) {
  const byNode = state?.attribution?.byNode || {};
  const att = byNode[nodeId] ?? byNode[Number(nodeId)];
  if (!att) return null;
  const rows = (Array.isArray(att.observables) ? att.observables : []).map((obs) => ({
    name: obs.name,
    mustMove: mustMove(obs.direction),
    moved: movedWord(obs.moved),
  }));
  const given = att.result === "clear";
  return {
    mechanism: att.mechanism,
    rows,
    verdict: given ? "given" : "refused",
    sentence: given ? "" : DICT.claimRefusedSentence.word,
  };
}

export function claimCardHtml(card) {
  if (!card) return "";
  const bannerClass =
    card.verdict === "given" ? "claim-banner claim-banner--given" : "claim-banner claim-banner--refused";
  const bannerWord =
    card.verdict === "given" ? DICT.claimGiven.word : DICT.claimRefused.word;
  const rows = card.rows
    .map(
      (r) =>
        `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.mustMove)}</td><td>${escapeHtml(r.moved)}</td></tr>`,
    )
    .join("");
  const sentence = card.sentence
    ? `<p class="claim-sentence">${escapeHtml(card.sentence)}</p>`
    : "";
  return `<section class="card claim-card">
    <h3>${escapeHtml(DICT.claimTitle.word)}</h3>
    <p>${escapeHtml(card.mechanism || "")}</p>
    <table class="claim-obs"><tbody>${rows}</tbody></table>
    <p class="${bannerClass}">${escapeHtml(bannerWord)}</p>
    ${sentence}
  </section>`;
}
