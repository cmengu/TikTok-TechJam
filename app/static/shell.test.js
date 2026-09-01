/** Tab-pane shell tests — node --test, static pins on index.html + app.js.
 *
 * The app shell (rail + header strip + run picker) stays fixed; every route
 * renders inside one viewport-capped scroll pane (.content-pane). The body
 * itself never scrolls — that is the point of the batch, so these tests pin
 * the structure that makes it true rather than a live layout measurement
 * (there is no DOM harness in this suite).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DICT } from "./copy.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INDEX = join(__dirname, "index.html");
const APP = join(__dirname, "app.js");

function loadIndex() {
  return readFileSync(INDEX, "utf8");
}

describe("tab-pane shell", () => {
  it("test_body_scroll_is_locked", () => {
    const html = loadIndex();
    assert.match(html, /<body class="body-scroll-lock">/);
    // The lock is real CSS, not just a class name: overflow hidden + a
    // viewport-height cap live on the .body-scroll-lock rule.
    const rule = html.match(/\.body-scroll-lock\s*{([^}]*)}/);
    assert.ok(rule, "missing .body-scroll-lock CSS rule");
    assert.match(rule[1], /overflow:\s*hidden/);
    assert.match(rule[1], /height:\s*100(vh|dvh)/);
  });

  it("test_view_renders_inside_the_content_pane", () => {
    const html = loadIndex();
    const pane = html.match(/<main id="pane" class="content-pane">([\s\S]*?)<\/main>/);
    assert.ok(pane, "missing <main id=\"pane\" class=\"content-pane\">");
    assert.match(pane[1], /<div id="view">/);
    // Shell chrome stays outside the pane: header strip and run picker are
    // fixed, only tab content scrolls.
    assert.equal(/<header id="header-strip">/.test(pane[1]), false);
    assert.equal(/hdr-run-picker/.test(pane[1]), false);
  });

  it("test_content_pane_is_the_scroll_container", () => {
    const html = loadIndex();
    const rule = html.match(/\.content-pane\s*{([^}]*)}/);
    assert.ok(rule, "missing .content-pane CSS rule");
    assert.match(rule[1], /overflow-y:\s*auto/);
    assert.match(rule[1], /min-height:\s*0/);
    assert.match(rule[1], /flex:\s*1\s+1\s+auto/);
  });

  it("test_route_change_resets_pane_scroll", () => {
    const src = readFileSync(APP, "utf8");
    // renderRoute puts the pane back at the top when the path actually
    // changes — but not on every store tick, which would fight the reader.
    assert.match(src, /pane\.scrollTop = 0/);
  });

  it("test_stale_server_banner_sits_in_the_fixed_shell", () => {
    // Fix list item 11: a 404 from an endpoint this page knows about means
    // the serving process predates the page. One dismissible banner in the
    // fixed shell (never scrolled away) instead of silent empty panels.
    const html = loadIndex();
    const banner = html.indexOf('<div id="stale-server-banner" hidden>');
    const pane = html.indexOf('<main id="pane"');
    assert.ok(banner !== -1, "missing stale-server banner markup");
    assert.ok(banner < pane, "banner must sit above the scroll pane");
    assert.match(html, /<button type="button" id="stale-server-dismiss"/);
  });

  it("test_stale_server_string_lives_in_the_dictionary", () => {
    assert.equal(
      DICT.staleServer.word,
      "this server is older than the page — restart it",
    );
    const src = readFileSync(APP, "utf8");
    // Every page-content fetch routes through the 404 check.
    assert.match(src, /function flagStaleServer/);
    assert.match(src, /\.then\(flagStaleServer\)/);
    assert.equal(src.includes("DICT.staleServer.word"), true);
  });

  it("test_inner_scroll_containers_survive", () => {
    const html = loadIndex();
    assert.match(html, /\.event-scroll\s*{[^}]*overflow-y:\s*auto/);
    assert.match(html, /\.protocol-scroll\s*{[^}]*overflow:\s*auto/);
  });
});
