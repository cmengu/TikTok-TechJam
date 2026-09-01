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
    // No hard-coded attempt id: a young run may not have attempt 3 yet (the
    // first-open case — the tour fires before events finish streaming), and
    // "#/run/3" then renders "no such attempt" with nothing to spotlight.
    // tourStopRoute() picks a real attempt from live state at draw time.
    route: "run",
    pickAttempt: true,
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

/**
 * Resolve a stop's route against live state. Literal routes pass through;
 * the journey stop (pickAttempt) targets the current best attempt, else the
 * first attempt created, else the bare attempts tree — never an id that
 * doesn't exist.
 */
export function tourStopRoute(stop, state) {
  if (!stop.pickAttempt) return stop.route;
  const id = state?.incumbent ?? state?.nodeOrder?.[0] ?? null;
  if (id == null) return "run";
  return `run/${encodeURIComponent(String(id))}`;
}

/**
 * Pane-relative scroll math for the spotlight. All inputs are viewport
 * coordinates (getBoundingClientRect) plus the pane's current scrollTop —
 * the body is scroll-locked, so window offsets never enter the picture.
 * Returns the pane scrollTop that centers the element, or null when the
 * element is already fully visible.
 */
export function paneScrollTarget({ paneTop, paneHeight, paneScrollTop, elTop, elHeight }) {
  const fits = elHeight <= paneHeight;
  const fullyVisible =
    elTop >= paneTop && elTop + elHeight <= paneTop + paneHeight;
  if (fits && fullyVisible) return null;
  const offset = fits ? (paneHeight - elHeight) / 2 : 0;
  return Math.max(0, paneScrollTop + (elTop - paneTop) - offset);
}
