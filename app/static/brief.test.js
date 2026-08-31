/** E2 Game-plan view-model tests — node --test, no DOM, no fetch. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildBrief } from "./brief.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");

describe("brief", () => {
  it("test_brief_view_model", () => {
    const ok = buildBrief({
      available: true,
      task: "synthetic",
      sections: [{ title: "Protocol", body: "frozen before the search." }],
    });
    assert.deepEqual(ok, {
      task: "synthetic",
      sections: [{ title: "Protocol", body: "frozen before the search." }],
    });

    assert.equal(buildBrief(null), null);
    assert.equal(buildBrief(undefined), null);
    assert.equal(buildBrief("nope"), null);
    assert.equal(buildBrief([]), null);
    assert.equal(buildBrief({}), null);
    assert.equal(buildBrief({ available: false, sections: [] }), null);
    assert.equal(buildBrief({ available: true }), null);
    assert.equal(
      buildBrief({ available: true, sections: "not-a-list" }),
      null,
    );
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Brief")'), false);
    assert.match(src, /hash:\s*"brief"/);
    assert.match(src, /render:\s*renderBrief/);
  });
});
