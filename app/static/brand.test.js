/** A1/A2 brand and sidebar tests — node --test, fixtures only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INDEX = join(__dirname, "index.html");

function loadIndex() {
  return readFileSync(INDEX, "utf8");
}

function titleText(html) {
  const m = html.match(/<title>([\s\S]*?)<\/title>/i);
  return m ? m[1].trim() : "";
}

function sidebarHtml(html) {
  const m = html.match(/<nav id="sidebar">([\s\S]*?)<\/nav>/);
  assert.ok(m, "sidebar nav is missing");
  return m[1];
}

function sidebarVisibleLabels(html) {
  const nav = sidebarHtml(html);
  const labels = [];
  for (const m of nav.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
    labels.push(m[1].trim());
  }
  for (const m of nav.matchAll(/<span class="nav-group-label">([\s\S]*?)<\/span>/g)) {
    labels.push(m[1].trim());
  }
  return labels;
}

const KNOWN_ROUTES = [
  "dashboard",
  "protocol",
  "brief",
  "research",
  "hypotheses",
  "run",
  "audit/replication",
  "audit/cost",
  "audit/reliability",
  "audit/monitors",
  "report",
  "the-rules",
  "learned",
];

describe("brand", () => {
  it("test_index_carries_luxmax_brand", () => {
    const html = loadIndex();
    // PR #70 respelled the wordmark "Lux Max"; either spacing is the brand.
    assert.match(html, /Lux ?Max/);
    assert.equal(/beating[- ]nise/i.test(html), false);
  });

  it("test_title_is_luxmax", () => {
    // Pinned to the wordmark spelling PR #70 shipped in the <h1>.
    assert.equal(titleText(loadIndex()), "Lux Max");
  });
});

describe("sidebar", () => {
  it("test_sidebar_labels_are_plain", () => {
    const labels = sidebarVisibleLabels(loadIndex());
    const banned = ["Hypotheses", "Replication", "Monitors", "Brief", "Reliability"];
    for (const word of banned) {
      assert.equal(
        labels.includes(word),
        false,
        `sidebar still shows "${word}"`,
      );
    }
  });

  it("test_route_attrs_unchanged", () => {
    const nav = sidebarHtml(loadIndex());
    const found = [...nav.matchAll(/data-route="([^"]+)"/g)].map((m) => m[1]);
    assert.deepEqual([...found].sort(), [...KNOWN_ROUTES].sort());
  });
});

