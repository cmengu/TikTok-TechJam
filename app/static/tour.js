/** V7 first-run tour. Pure module — no DOM. */

import { DICT } from "./copy.js";
import { escapeHtml } from "./chip.js";

export const TOUR_FLAG = "luxmax_tour_done";

export const TOUR_STOPS = [
  {
    route: "brief",
    anchor: null,
    title: DICT.tourBriefTitle.word,
    body: DICT.tourBriefBody.word,
  },
  {
    route: "run",
    anchor: null,
    title: DICT.tourRunTitle.word,
    body: DICT.tourRunBody.word,
  },
  {
    route: "run/3",
    anchor: "journey-strip",
    title: DICT.tourJourneyTitle.word,
    body: DICT.tourJourneyBody.word,
  },
  {
    route: "learned",
    anchor: null,
    title: DICT.tourMemoryTitle.word,
    body: DICT.tourMemoryBody.word,
  },
  {
    route: "dashboard",
    anchor: "data-dashboard-hero",
    title: DICT.tourHeroTitle.word,
    body: DICT.tourHeroBody.word,
  },
];

export function shouldShowTour(storage) {
  try {
    return storage.getItem(TOUR_FLAG) !== "1";
  } catch {
    return false;
  }
}

export function markTourDone(storage) {
  try {
    storage.setItem(TOUR_FLAG, "1");
  } catch {
    /* never block the app on storage */
  }
}

export function tourOverlayHtml(stop, index, total) {
  const n = index + 1;
  return `<div class="tour-card" role="dialog" aria-modal="true">
    <p class="stat-caption">${n} of ${total}</p>
    <h2>${escapeHtml(stop.title)}</h2>
    <p>${escapeHtml(stop.body)}</p>
    <p class="tour-actions">
      <button type="button" data-tour="next">Next</button>
      <button type="button" data-tour="skip">Skip</button>
    </p>
  </div>`;
}
