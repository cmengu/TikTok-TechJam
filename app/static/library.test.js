/** E5 Library view-model tests — node --test, fixture only (no DOM, no fetch). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initial, reduce } from "./reducer.js";
import { buildLibrary, libraryPageHtml } from "./library.js";

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
    // the covers script filled manifest pdf paths, so a local PDF now beats
    // the arXiv abs link (event-carried urls still win over both)
    assert.equal(deepfm.action.kind, "pdf");
    assert.equal(deepfm.action.href, "/papers/pdfs/arxiv-1703-04247.pdf");
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

describe("library llm-usage de-pollution", () => {
  const LLM_USAGE = {
    schema_version: 1,
    seq: 9001,
    t: "2026-08-31T17:32:22.153Z",
    type: "research_source",
    id: "usage-0-coding",
    title: "llm usage",
    node: 0,
    cost: { gpu_s: 0.0, tokens_in: 17244, tokens_out: 9069, slice: "coding" },
    summary: "llm coding: 17244 in / 9069 out tokens",
  };

  it("test_llm_usage_rows_never_reach_the_library", () => {
    const events = [...loadJsonl(FIXTURE), LLM_USAGE];
    const lib = buildLibrary(fold(events), loadManifest());
    assert.ok(lib.length > 0);
    assert.equal(
      lib.find((p) => p.title === "llm usage"),
      undefined,
    );
  });
});

describe("library card grid", () => {
  const paper = (o = {}) => ({
    title: "DeepFM: A Factorization-Machine based Neural Network",
    venue: "IJCAI",
    year: 2017,
    one_liner: "Factorization machines plus a deep net.",
    action: { kind: "pdf", href: "/papers/pdfs/arxiv-1703-04247.pdf" },
    cover: "/papers/thumbs/arxiv-1703-04247.png",
    ideas: [],
    tokens: 0,
    ...o,
  });

  it("test_build_carries_cover_from_manifest_thumb", () => {
    const lib = buildLibrary(fold(loadJsonl(FIXTURE)), [
      {
        title: "DeepFM",
        match: ["DeepFM"],
        url: "https://arxiv.org/abs/1703.04247",
        pdf: "pdfs/arxiv-1703-04247.pdf",
        thumb: "thumbs/arxiv-1703-04247.png",
        year: 2017,
        venue: "IJCAI",
        one_liner: "x",
      },
    ]);
    const deepfm = lib.find((p) => p.title === "DeepFM");
    assert.ok(deepfm);
    assert.equal(deepfm.cover, "/papers/thumbs/arxiv-1703-04247.png");
  });

  it("test_card_with_cover_renders_image_and_title_overlay", () => {
    const html = libraryPageHtml([paper()]);
    assert.match(html, /paper-grid/);
    assert.match(html, /paper-card/);
    assert.match(html, /<img[^>]*src="\/papers\/thumbs\/arxiv-1703-04247\.png"/);
    assert.match(html, /paper-cover-overlay/);
    assert.match(html, /IJCAI · 2017/);
    assert.match(html, /Factorization machines plus a deep net\./);
    // the whole card is the click-through to the PDF
    assert.match(html, /href="\/papers\/pdfs\/arxiv-1703-04247\.pdf"/);
  });

  it("test_card_without_cover_renders_placeholder_spine", () => {
    const html = libraryPageHtml([
      paper({
        title: "Factorization Machines",
        venue: "ICDM",
        year: 2010,
        cover: null,
        action: { kind: "link", href: "https://ieeexplore.ieee.org/document/5694074" },
      }),
    ]);
    assert.match(html, /paper-spine/);
    assert.doesNotMatch(html, /<img/);
    assert.match(html, /Factorization Machines/);
    assert.match(html, /ICDM/);
  });

  it("test_card_markup_escapes_titles", () => {
    const html = libraryPageHtml([
      paper({ title: '<script>alert(1)</script>', cover: null }),
    ]);
    assert.doesNotMatch(html, /<script>alert/);
  });
});
