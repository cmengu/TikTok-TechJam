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
