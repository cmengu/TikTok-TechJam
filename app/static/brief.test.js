/** E2 Game-plan view-model tests — node --test, no DOM, no fetch. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildBrief, briefPageHtml } from "./brief.js";

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

  it("test_page_never_renders_the_backend_spec_sections", () => {
    // /runs/{id}/brief serves context/Backend_plan.md verbatim — a backend
    // spec companion, not a game plan. The page keeps the goal/rules intro
    // and drops the fetched md sections entirely (user order, 1 Sep).
    const vm = buildBrief({
      available: true,
      task: "kuairand",
      sections: [
        { title: "Harness Decisions", body: "## Sections\n- A · Files and how they connect" },
      ],
    });
    const html = briefPageHtml(vm);
    assert.ok(html.includes("The goal"));
    assert.ok(html.includes("The rules"));
    assert.ok(html.includes("task kuairand"));
    assert.equal(html.includes("Harness Decisions"), false);
    assert.equal(html.includes("Files and how they connect"), false);
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Brief")'), false);
    assert.match(src, /hash:\s*"brief"/);
    assert.match(src, /render:\s*renderBrief/);
  });
});
