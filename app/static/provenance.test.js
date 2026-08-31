/** V4 provenance tests — node --test, fixture only. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { DICT } from "./copy.js";
import {
  MEASURED,
  stampFor,
  stampHtml,
  provenanceTileHtml,
} from "./provenance.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");

function loadJsonl(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

const EVERY_MEASURED = Object.fromEntries([...MEASURED].map((k) => [k, 1]));

describe("provenance", () => {
  it("test_measured_list_matches_fixture", () => {
    const ev = { type: "measurement", producer: "measure", ...EVERY_MEASURED };
    for (const key of MEASURED) {
      assert.ok(key in ev, `fixture event missing MEASURED field ${key}`);
    }
    assert.equal(stampFor(ev), "measured");
  });

  it("test_measured_requires_producer", () => {
    const ev = { type: "verdict", delta_mean: 0.01, producer: "tree" };
    assert.equal(stampFor(ev), null);
  });

  it("test_forecast_only_on_queued", () => {
    assert.equal(
      stampFor({ type: "hypothesis_queued", expected_gain: 0.02 }),
      "forecast",
    );
    assert.equal(
      stampFor({ type: "verdict", expected_gain: 0.02 }),
      null,
    );
  });

  it("test_counts_slice_folds", () => {
    const events = loadJsonl(FIXTURE);
    let measured = 0;
    let forecasts = 0;
    for (const ev of events) {
      const kind = stampFor(ev);
      if (kind === "measured") measured += 1;
      if (kind === "forecast") forecasts += 1;
    }
    const state = fold(events);
    assert.equal(state.provenance.measured, measured);
    assert.equal(state.provenance.forecasts, forecasts);
    assert.ok(measured > 0, "fixture should carry measured events");
  });

  it("test_tile_renders_counts", () => {
    const html = provenanceTileHtml({ measured: 4, forecasts: 2 });
    assert.match(html, /4 measured/);
    assert.match(html, /2 forecasts/);
    assert.ok(html.includes(DICT.provenanceCaption.word));
    assert.equal(html.includes("0 exceptions"), true);
    assert.equal(
      /0 exceptions possible/.test(DICT.provenanceCaption.word),
      true,
    );
  });

  it("test_pure", () => {
    const ev = { type: "measurement", producer: "measure", value: 1 };
    assert.equal(stampFor(ev), stampFor(ev));
    assert.equal(stampHtml("measured"), stampHtml("measured"));
  });
});
