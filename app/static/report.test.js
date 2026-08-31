/** E8 Summary view-model tests — node --test, no DOM, no fetch. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildReport, buildReportHero } from "./report.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");

describe("report", () => {
  it("test_report_view_model", () => {
    assert.deepEqual(
      buildReport({ available: true, markdown: "# hi" }),
      { markdown: "# hi" },
    );
    assert.equal(buildReport(null), null);
    assert.equal(buildReport({ available: false, reason: "not finished" }), null);
    assert.equal(buildReport({ available: true }), null);
  });

  it("test_report_hero_before_score", () => {
    const empty = buildReportHero({ available: false });
    assert.equal(empty.score, "—");
    const ok = buildReportHero({
      available: true,
      primary: 0.6041,
      claim_level: "L4-v",
    });
    assert.equal(ok.score, "0.6041");
    assert.equal(ok.trustWord, "fully verified");
  });

  it("test_route_replaced", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(src.includes('renderStub("Report")'), false);
    assert.match(src, /hash:\s*"report"/);
    assert.match(src, /render:\s*renderReport/);
  });
});
