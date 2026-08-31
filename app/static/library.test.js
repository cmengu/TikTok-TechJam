/** E5 Library view-model tests — node --test, fixture only (no DOM, no fetch). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { buildLibrary } from "./library.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(__dirname, "..", "..", "tests", "fixtures", "fake-events.jsonl");
const MANIFEST = join(__dirname, "..", "..", "papers", "manifest.json");
const APP = join(__dirname, "app.js");

function loadJsonl(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function fold(events) {
  return events.reduce((s, ev) => reduce(s, ev), initial());
}

function loadManifest() {
  return JSON.parse(readFileSync(MANIFEST, "utf8"));
}

describe("library", () => {
  it("test_join_matched_title", () => {
    const lib = buildLibrary(fold(loadJsonl(FIXTURE)), loadManifest());
    const deepfm = lib.find((p) => p.title === "DeepFM");
    assert.ok(deepfm);
    assert.equal(deepfm.year, 2017);
    assert.equal(deepfm.venue, "IJCAI");
    assert.equal(deepfm.action.kind, "link");
    assert.equal(deepfm.action.href, "https://arxiv.org/abs/1703.04247");
  });

  it("test_unmatched_falls_to_scholar", () => {
    const lib = buildLibrary(fold(loadJsonl(FIXTURE)), loadManifest());
    const sweep = lib.find((p) => p.title === "tuner sweep");
    assert.ok(sweep);
    assert.equal(sweep.action.kind, "search");
    assert.equal(
      sweep.action.href,
      "https://scholar.google.com/scholar?q=" + encodeURIComponent("tuner sweep"),
    );
    assert.equal(sweep.year, null);
    assert.equal(sweep.venue, null);
  });

  it("test_event_url_beats_manifest", () => {
    const lib = buildLibrary(fold(loadJsonl(FIXTURE)), loadManifest());
    const wide = lib.find((p) => p.title === "Wide & Deep");
    assert.ok(wide);
    assert.equal(wide.action.kind, "link");
    assert.equal(wide.action.href, "https://arxiv.org/abs/1606.07792");
    const twisted = [
      {
        title: "Wide & Deep Learning for Recommender Systems",
        match: ["Wide & Deep"],
        url: "https://example.invalid/not-the-event",
        pdf: null,
        year: 2016,
        venue: "DLRS",
        one_liner: "x",
      },
    ];
    const again = buildLibrary(fold(loadJsonl(FIXTURE)), twisted);
    const wide2 = again.find((p) => p.title === "Wide & Deep");
    assert.equal(wide2.action.href, "https://arxiv.org/abs/1606.07792");
    assert.notEqual(wide2.action.href, twisted[0].url);
  });

  it("test_ideas_and_outcomes_attach", () => {
    const state = fold(loadJsonl(FIXTURE));
    const withNode = {
      ...state,
      research: {
        ...state.research,
        sources: state.research.sources.map((s) =>
          s.title === "Wide & Deep" ? { ...s, node: 3 } : s,
        ),
      },
    };
    const lib = buildLibrary(withNode, loadManifest());
    const wide = lib.find((p) => p.title === "Wide & Deep");
    assert.equal(wide.ideas.length, 1);
    assert.equal(wide.ideas[0].id, "h-train-1");
    assert.equal(wide.ideas[0].pattern, "lr-schedule");
    assert.equal(wide.ideas[0].outcome, "accepted");
    const unmatched = lib.find((p) => p.title === "DeepFM");
    assert.deepEqual(unmatched.ideas, []);
  });

  it("test_empty_library", () => {
    assert.deepEqual(buildLibrary(initial(), loadManifest()), []);
    assert.deepEqual(buildLibrary({ research: { sources: [] } }, []), []);
    assert.deepEqual(buildLibrary(null, loadManifest()), []);
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Research")'), false);
    assert.match(src, /hash:\s*"research"/);
    assert.match(src, /render:\s*renderLibrary/);
  });
});
