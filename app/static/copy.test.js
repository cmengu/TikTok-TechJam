/** C1 copy.js dictionary tests — node --test, no DOM. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { STATES } from "./reducer.js";
import {
  BANNED,
  DICT,
  attributionLabel,
  claimLabel,
  fmtDelta,
  fmtDuration,
  fmtScore,
  fmtTokens,
  claimReasonLabel,
  eventTypeLabel,
  EVENT_TYPE_LABELS,
  fmtPublished,
  levelLabel,
  moveLabel,
  rungLabel,
  stateLabel,
} from "./copy.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = join(__dirname, "app.js");

const GERUND_ALLOWLIST = new Set([
  "accepted",
  "declined",
  "retrying",
  "shelved",
  "disqualified",
  "crashed",
  "screening",
  "building",
  "repeating",
  "fixing",
]);

function bannedRe() {
  return new RegExp(`\\b(?:${BANNED.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "i");
}

describe("copy", () => {
  it("test_every_state_has_a_label", () => {
    for (const state of STATES) {
      const label = stateLabel(state);
      assert.equal(typeof label.word, "string");
      assert.ok(label.word.length > 0, `empty word for ${state}`);
      assert.ok(
        GERUND_ALLOWLIST.has(label.word),
        `${state} → ${label.word} not in gerund allowlist`,
      );
    }
  });

  it("test_unknown_term_passes_through", () => {
    assert.deepEqual(stateLabel("mystery"), { word: "mystery", hint: null });
    assert.deepEqual(moveLabel("warp"), { word: "warp", hint: null });
    assert.deepEqual(levelLabel("gamma"), { word: "gamma", hint: null });
    assert.deepEqual(rungLabel("ladder"), { word: "ladder", hint: null });
    assert.deepEqual(claimLabel("L9"), { word: "L9", hint: null });
  });

  it("test_labels_contain_no_banned_words", () => {
    const re = bannedRe();
    const samples = [
      ...STATES.map(stateLabel),
      moveLabel("draft"),
      moveLabel("improve"),
      moveLabel("debug"),
      moveLabel(null),
      levelLabel("omega"),
      levelLabel("v_sem"),
      levelLabel("smoke"),
      rungLabel("screen"),
      rungLabel("replicate"),
      claimLabel("L4-v"),
      claimLabel("L4-m"),
      claimLabel("L3"),
    ];
    for (const label of samples) {
      assert.equal(re.test(label.word), false, `banned in word: ${label.word}`);
      if (label.hint != null) {
        assert.equal(re.test(label.hint), false, `banned in hint: ${label.hint}`);
      }
    }
    for (const [key, label] of Object.entries(DICT)) {
      assert.equal(re.test(label.word), false, `banned in DICT.${key}.word: ${label.word}`);
      if (label.hint != null) {
        assert.equal(re.test(label.hint), false, `banned in DICT.${key}.hint: ${label.hint}`);
      }
    }
  });

  it("test_formatters", () => {
    assert.equal(fmtScore(0.60414), "0.6041");
    assert.equal(fmtScore(null), "—");
    assert.equal(fmtDelta(0.004), "+0.0040");
    assert.equal(fmtDelta(-0.002), "-0.0020");
    assert.equal(fmtDelta(null), "—");
    assert.equal(fmtTokens(12400), "12.4k");
    assert.equal(fmtDuration(94), "1m 34s");
  });

  it("test_zero_is_not_a_dash", () => {
    assert.equal(fmtScore(0), "0.0000");
    assert.equal(fmtTokens(0), "0");
    assert.notEqual(fmtScore(0), "—");
    assert.notEqual(fmtTokens(0), "—");
  });

  it("test_rung_heading_is_plain", () => {
    const label = DICT.rungHeading;
    assert.equal(typeof label.word, "string");
    assert.ok(label.word.length > 0);
    assert.equal(bannedRe().test(label.word), false, `banned in heading: ${label.word}`);
    assert.notEqual(label.word.toLowerCase(), "rung");
  });

  it("test_app_templates_do_not_render_rung_heading", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(
      src.includes("<h2>Rung</h2>"),
      false,
      "app.js still hard-codes <h2>Rung</h2> — use DICT.rungHeading",
    );
  });

  it("test_attribution_label_maps_clear_and_unclear", () => {
    assert.equal(attributionLabel("clear"), "explained");
    assert.equal(attributionLabel("unclear"), "unexplained");
  });

  it("test_unknown_attribution_does_not_leak", () => {
    assert.equal(attributionLabel("mystery"), "unexplained");
    assert.equal(attributionLabel("clearish"), "unexplained");
    assert.equal(attributionLabel(null), "unexplained");
  });

  it("test_oracle_gap_heading_is_plain", () => {
    const label = DICT.oracleGapHeading;
    assert.equal(typeof label.word, "string");
    assert.ok(label.word.length > 0);
    assert.equal(bannedRe().test(label.word), false, `banned in heading: ${label.word}`);
    assert.equal(label.word, "Hidden-check gap");
  });

  it("test_app_templates_do_not_render_oracle_gap_heading", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(
      src.includes("<h2>Oracle gap"),
      false,
      "app.js still hard-codes <h2>Oracle gap — use DICT.oracleGapHeading",
    );
  });

  it("test_baseline_significance_note_is_plain", () => {
    const label = DICT.baselineSignificanceNote;
    assert.equal(typeof label.word, "string");
    assert.ok(label.word.length > 0);
    assert.equal(bannedRe().test(label.word), false, `banned in note: ${label.word}`);
    assert.equal(
      label.word,
      "an accepted win's noise bar tests whether the repeat test agreed with the quick test, not whether the lead over the published baseline clears run-to-run noise — nothing yet compares the current best's score against the published baseline for significance",
    );
  });

  it("test_app_templates_do_not_hardcode_baseline_significance_note", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(
      src.includes("a promoted verdict's band tests"),
      false,
      "app.js still hard-codes the vs-baseline hover — use DICT.baselineSignificanceNote",
    );
  });

  it("test_since_win_title_is_plain", () => {
    const label = DICT.sinceWinTitle;
    assert.equal(typeof label.word, "string");
    assert.ok(label.word.length > 0);
    assert.equal(bannedRe().test(label.word), false, `banned in title: ${label.word}`);
    assert.equal(
      label.word,
      "counts decisions in the log since the last accepted win — the run itself does not yet track rounds without improvement",
    );
  });

  it("test_app_templates_do_not_hardcode_since_win_title", () => {
    const src = readFileSync(APP, "utf8");
    assert.equal(
      src.includes("verdicts since last promotion"),
      false,
      "app.js still hard-codes the since-win line — use DICT.sinceWinTitle",
    );
  });

  it("test_check_labels_are_plain", () => {
    assert.equal(DICT.checkStatic.word, "free pattern check");
    assert.equal(DICT.checkLlm.word, "one model reading");
    assert.equal(bannedRe().test(DICT.checkStatic.word), false);
    assert.equal(bannedRe().test(DICT.checkLlm.word), false);
  });

  it("test_rulebook_header_carries_count_slot", () => {
    assert.ok(DICT.rulebookHeader.word.includes("{n}"));
    assert.equal(bannedRe().test(DICT.rulebookHeader.word.replace("{n}", "18")), false);
  });
});

describe("pre-G2 renderer copy entries", () => {
  const entries = ["oracleGapHeading", "baselineSignificanceNote", "sinceWinTitle"];

  it("test_renderer_copy_entries_exist", () => {
    for (const key of entries) {
      assert.equal(typeof DICT[key].word, "string");
      assert.ok(DICT[key].word.length > 0);
    }
    assert.equal(DICT.oracleGapHeading.word, "Hidden-check gap");
  });

  it("test_renderer_copy_entries_speak_no_jargon", () => {
    // Refusal twin: a dictionary entry that itself carries a banned term
    // would launder jargon straight back onto the page.
    for (const key of entries) {
      for (const term of BANNED) {
        assert.ok(
          !new RegExp(`\\b${term}\\b`, "i").test(DICT[key].word),
          `${key} contains banned term "${term}"`,
        );
      }
    }
  });
});

describe("claimReasonLabel", () => {
  it("test_no_promotions_translates", () => {
    assert.equal(
      claimReasonLabel("no promotions on the log"),
      "no accepted wins on the log yet",
    );
  });

  it("test_counted_promotions_translate", () => {
    assert.equal(
      claimReasonLabel("2 of 3 promotions carry oracle_delta"),
      "2 of 3 accepted wins carry a hidden-check reading",
    );
  });

  it("test_unknown_reason_passes_through_and_null_is_empty", () => {
    assert.equal(claimReasonLabel("hand-written reason"), "hand-written reason");
    assert.equal(claimReasonLabel(null), "");
  });
});

describe("fmtPublished", () => {
  it("test_metric_map_reads_as_pairs", () => {
    assert.equal(
      fmtPublished({ gauc: 0.6674, ndcg_at_5: 0.5357, primary: 0.6016 }),
      "gauc 0.6674 \u00b7 ndcg@5 0.5357 \u00b7 primary 0.6016",
    );
  });

  it("test_scalars_pass_through", () => {
    assert.equal(fmtPublished(0.4834), "0.4834");
    assert.equal(fmtPublished("synthetic-baseline-v1"), "synthetic-baseline-v1");
  });

  it("test_object_never_reaches_string", () => {
    // Refuse twin for fix list item 5: any structured value, however nested,
    // must never render as "[object Object]".
    const gnarly = [
      { valid: { gauc: 0.6, deep: { deeper: 1 } } },
      { oracle_ceiling: { valid: 0.8484, test: 0.8645 } },
      [{ a: 1 }, { b: [2, { c: 3 }] }],
      {},
    ];
    for (const value of gnarly) {
      assert.ok(!fmtPublished(value).includes("[object Object]"));
    }
  });
});

describe("eventTypeLabel", () => {
  it("test_known_types_read_as_plain_words", () => {
    assert.equal(eventTypeLabel("research_source", 2), "papers");
    assert.equal(eventTypeLabel("research_source", 1), "paper");
    assert.equal(eventTypeLabel("verdict", 3), "decisions");
    assert.equal(eventTypeLabel("node_created", 2), "attempts built");
  });

  it("test_unknown_types_fall_back_to_events", () => {
    assert.equal(eventTypeLabel("some_new_type", 2), "events");
    assert.equal(eventTypeLabel(undefined, 1), "event");
  });

  it("test_every_label_clears_the_banned_list", () => {
    const bannedRe = new RegExp(`\\b(?:${BANNED.join("|")})\\b`, "i");
    for (const [type, entry] of Object.entries(EVENT_TYPE_LABELS)) {
      assert.ok(!bannedRe.test(entry.one), `${type}: ${entry.one}`);
      assert.ok(!bannedRe.test(entry.many), `${type}: ${entry.many}`);
    }
  });
});
