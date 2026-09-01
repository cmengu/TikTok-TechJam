/** V7 tour tests — node --test, no DOM. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  TOUR_STOPS,
  shouldShowTour,
  markTourDone,
  tourOverlayHtml,
  tourStopRoute,
  paneScrollTarget,
} from "./tour.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");
const INDEX = join(__dirname, "index.html");

describe("tour", () => {
  it("test_stops_routes_exist", () => {
    const src = readFileSync(APP, "utf8");
    for (const stop of TOUR_STOPS) {
      const hash = stop.route.split("/")[0];
      assert.ok(
        src.includes(`hash: "${hash}"`),
        `tour stop ${stop.route} missing from ROUTES`,
      );
    }
  });

  it("test_should_show_false_on_storage_throw", () => {
    const storage = {
      getItem() {
        throw new Error("blocked");
      },
    };
    assert.equal(shouldShowTour(storage), false);
  });

  it("test_dismiss_persists", () => {
    const store = new Map();
    const storage = {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => store.set(k, v),
    };
    assert.equal(shouldShowTour(storage), true);
    markTourDone(storage);
    assert.equal(shouldShowTour(storage), false);
  });

  it("test_replay_affordance", () => {
    const html = readFileSync(INDEX, "utf8");
    assert.match(html, /id="tour-replay"/);
    const src = readFileSync(APP, "utf8");
    assert.match(src, /tour-replay/);
  });

  it("test_two_sentence_cap", () => {
    for (const stop of TOUR_STOPS) {
      const sentences = stop.body.split(/(?<=[.?!])\s+/).filter(Boolean);
      assert.ok(
        sentences.length <= 2,
        `${stop.route} body has ${sentences.length} sentences`,
      );
    }
  });

  it("test_overlay_html", () => {
    const html = tourOverlayHtml(TOUR_STOPS[0], 0, 5);
    assert.match(html, /1 of 5/);
    assert.ok(html.includes(TOUR_STOPS[0].title));
  });
});

// --- V7 tour fixes: the journey stop must point at an attempt that exists,
// and spotlight targets must be scrolled into view inside the pane (the body
// is scroll-locked since the content-pane rework; window scrolling is dead).

describe("tour attempt step", () => {
  const journey = TOUR_STOPS.find((s) => s.anchor === "journey-strip");

  it("test_no_stop_hard_codes_an_attempt_id", () => {
    for (const stop of TOUR_STOPS) {
      assert.doesNotMatch(stop.route, /\//, `${stop.route} hard-codes a sub-path`);
    }
    assert.ok(journey, "journey stop exists");
    assert.equal(journey.pickAttempt, true);
  });

  it("test_journey_stop_prefers_the_current_best", () => {
    const state = { incumbent: 2, nodeOrder: [1, 2, 3] };
    assert.equal(tourStopRoute(journey, state), "run/2");
  });

  it("test_journey_stop_falls_back_to_the_first_attempt", () => {
    const state = { incumbent: null, nodeOrder: [1, 2] };
    assert.equal(tourStopRoute(journey, state), "run/1");
  });

  it("test_journey_stop_with_no_attempts_shows_the_tree", () => {
    assert.equal(tourStopRoute(journey, { incumbent: null, nodeOrder: [] }), "run");
    assert.equal(tourStopRoute(journey, null), "run");
  });

  it("test_literal_stops_pass_through_untouched", () => {
    const brief = TOUR_STOPS[0];
    assert.equal(tourStopRoute(brief, { incumbent: 2, nodeOrder: [1] }), brief.route);
  });

  it("test_route_ids_are_uri_encoded", () => {
    const state = { incumbent: "a/b", nodeOrder: [] };
    assert.equal(tourStopRoute(journey, state), "run/a%2Fb");
  });
});

describe("tour pane scroll", () => {
  // paneScrollTarget: viewport-relative pane box + element box in, the pane
  // scrollTop that centers the element out — or null when no scroll needed.
  const pane = { paneTop: 100, paneHeight: 600, paneScrollTop: 50 };

  it("test_element_already_visible_means_no_scroll", () => {
    const t = paneScrollTarget({ ...pane, elTop: 200, elHeight: 100 });
    assert.equal(t, null);
  });

  it("test_element_below_the_fold_centers_in_the_pane", () => {
    // element sits 900px below the pane top (viewport-relative 1000)
    const t = paneScrollTarget({ ...pane, elTop: 1000, elHeight: 100 });
    // scrollTop + (elTop - paneTop) - (paneHeight - elHeight) / 2
    assert.equal(t, 50 + 900 - 250);
  });

  it("test_element_above_the_viewport_scrolls_back_up", () => {
    const t = paneScrollTarget({ ...pane, elTop: -300, elHeight: 100 });
    assert.equal(t, Math.max(0, 50 + -400 - 250));
    assert.equal(t, 0);
  });

  it("test_element_taller_than_pane_aligns_to_its_top", () => {
    const t = paneScrollTarget({ ...pane, elTop: 1000, elHeight: 900 });
    assert.equal(t, 50 + 900);
  });

  it("test_app_scrolls_the_pane_not_the_window", () => {
    const src = readFileSync(APP, "utf8");
    assert.match(src, /paneScrollTarget\(/);
    assert.match(src, /tourStopRoute\(/);
    // the overlay forwards wheel to the pane — the fixed backdrop otherwise
    // chains scroll into the locked body and the pane never moves
    assert.match(src, /addEventListener\(\s*"wheel"/);
    assert.doesNotMatch(src, /window\.scrollTo/);
  });
});
