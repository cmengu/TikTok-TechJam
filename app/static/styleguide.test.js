/** B2 styleguide + chip-state tests — node --test, fixtures only (no Python). */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INDEX = join(__dirname, "index.html");
const APP = join(__dirname, "app.js");

function load(path) {
  return readFileSync(path, "utf8");
}

const CHIP_MODIFIERS = [
  "accepted",
  "declined",
  "retrying",
  "shelved",
  "disqualified",
  "crashed",
  "live",
];

describe("styleguide", () => {
  it("test_styleguide_route_exists", () => {
    const src = load(APP);
    assert.match(src, /hash:\s*"styleguide"/);
    assert.match(src, /render:\s*renderStyleguide/);
    assert.match(src, /function renderStyleguide/);
  });

  it("test_chip_state_modifiers_defined", () => {
    const css = load(INDEX);
    for (const mod of CHIP_MODIFIERS) {
      assert.match(
        css,
        new RegExp(`\\.chip-state--${mod}\\b`),
        `missing .chip-state--${mod}`,
      );
    }
  });
});
