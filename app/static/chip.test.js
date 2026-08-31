/** C3 chipHtml hint tests — node --test, no DOM. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { chipHtml } from "./chip.js";

describe("chip", () => {
  it("test_chip_carries_hint", () => {
    const html = chipHtml(
      { word: "accepted", hint: "real improvement" },
      "accepted",
    );
    assert.match(html, /class="chip-state chip-state--accepted"/);
    assert.match(html, /data-hint="real improvement"/);
    assert.match(html, />accepted</);
  });

  it("test_chip_without_hint_omits_attr", () => {
    const html = chipHtml({ word: "accepted", hint: null }, "accepted");
    assert.equal(html.includes("data-hint"), false);
    assert.match(html, /class="chip-state chip-state--accepted"/);
    assert.match(html, />accepted</);
  });
});
