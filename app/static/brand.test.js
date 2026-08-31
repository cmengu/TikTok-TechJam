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

describe("brand", () => {
  it("test_index_carries_luxmax_brand", () => {
    const html = loadIndex();
    assert.match(html, /LuxMax/);
    assert.equal(/beating[- ]nise/i.test(html), false);
  });

  it("test_title_is_luxmax", () => {
    assert.equal(titleText(loadIndex()), "LuxMax");
  });
});
