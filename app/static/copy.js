/** LuxMax language layer — pure dictionary and formatters. No DOM, no imports. */

export const DICT = {
  node: {
    word: "attempt",
    hint: "one model variant the agent built and tested",
  },
  hypothesis: {
    word: "idea",
    hint: "a proposed change, usually taken from a paper",
  },
  research_source: {
    word: "paper",
    hint: "a publication the agent read",
  },
  screen: {
    word: "quick test",
    hint: "one fast training run to see if the idea has promise",
  },
  replicate: {
    word: "repeat test",
    hint: "three re-runs with shuffled randomness — a win must survive all three",
  },
  oracle: {
    word: "hidden check",
    hint: "scored on data the model never saw; budget of 12 uses",
  },
  holdout: {
    word: "hidden check",
    hint: "scored on data the model never saw; budget of 12 uses",
  },
  verdict: {
    word: "decision",
    hint: "accept, decline, retry, or disqualify",
  },
  promoted: { word: "accepted", hint: "real improvement" },
  rejected: { word: "declined", hint: "no real improvement" },
  inconclusive: {
    word: "retrying",
    hint: "results disagreed, queued again (3 tries, then shelved)",
  },
  retired: {
    word: "shelved",
    hint: "results disagreed, queued again (3 tries, then shelved)",
  },
  leaked: { word: "disqualified", hint: "touched forbidden data" },
  failed: { word: "crashed", hint: "training broke" },
  clear: {
    word: "explained",
    hint: "an unexplained win is never accepted",
  },
  unclear: {
    word: "unexplained",
    hint: "an unexplained win is never accepted",
  },
  gap_alarm: {
    word: "overfit warning",
    hint: "three wins in a row looked worse on the hidden check",
  },
  "L4-v": {
    word: "fully verified",
    hint: "how much to trust the headline number",
  },
  "L4-m": {
    word: "verified*",
    hint: "how much to trust the headline number",
  },
  L3: {
    word: "no wins yet",
    hint: "how much to trust the headline number",
  },
  primary: {
    word: "score",
    hint: "ranking quality (mean of GAUC, nDCG@5)",
  },
  band: {
    word: "noise bar",
    hint: "smaller-than-this is luck",
  },
  rungHeading: {
    word: "Testing stage",
    hint: "how much to trust the headline number",
  },
  bandLegacyReason: {
    word: "the noise bar came from the demo script's old format — no real threshold was reported",
    hint: "smaller-than-this is luck",
  },
  bandMissingReason: {
    word: "no noise bar was reported for this decision",
    hint: "smaller-than-this is luck",
  },
  bandUnknownKindReason: {
    word: "this decision carries no test kind — which comparison was made is unknown",
    hint: "smaller-than-this is luck",
  },
  bandUnavailableReason: {
    word: "the threshold for this comparison is unavailable",
    hint: "smaller-than-this is luck",
  },
  oracleGapHeading: {
    word: "Hidden-check gap",
    hint: "how far the reported score sits from the hidden check",
  },
  baselineSignificanceNote: {
    word: "an accepted win's noise bar tests whether the repeat test agreed with the quick test, not whether the lead over the published baseline clears run-to-run noise — nothing yet compares the current best's score against the published baseline for significance",
    hint: null,
  },
  sinceWinTitle: {
    word: "counts decisions in the log since the last accepted win — the run itself does not yet track rounds without improvement",
    hint: null,
  },
  incumbent: {
    word: "current best",
    hint: "the model every attempt must beat",
  },
  draft: { word: "new idea", hint: "the three kinds of next move" },
  improve: { word: "build on best", hint: "the three kinds of next move" },
  debug: { word: "fix a crash", hint: "the three kinds of next move" },
  omega: {
    word: "rulebook",
    hint: "three free gates before any GPU is spent",
  },
  v_sem: {
    word: "honesty",
    hint: "three free gates before any GPU is spent",
  },
  smoke: {
    word: "dry-run check",
    hint: "three free gates before any GPU is spent",
  },
  lesson: { word: "note", hint: "what the agent learned" },
  forbidden: {
    word: "banned idea",
    hint: "ideas it refuses to retry",
  },
  checkStatic: {
    word: "free pattern check",
    hint: "a regex over the candidate, no model",
  },
  checkLlm: {
    word: "one model reading",
    hint: "one model judges the candidate against the contract",
  },
  rulebookHeader: {
    word: "These {n} rules are the whole contract. The candidate reads this file; the checks below run this file. Same document.",
    hint: null,
  },
  rulebookUnavailable: {
    word: "the contract file is unreadable",
    hint: null,
  },
  wallCaption: {
    word: "The final score is measured behind this wall. The searching agent cannot see through it, and every look is counted against a budget.",
    hint: null,
  },
  wallMeter: {
    word: "Hidden check: visited {v} of {cap}",
    hint: "scored on data the model never saw; budget of 12 uses",
  },
  wallQueries: {
    word: "Times the search consulted the test signal: {q}",
    hint: null,
  },
  wallDigests: {
    word: "Data fingerprints: recorded at load ✓",
    hint: null,
  },
  stampMeasured: { word: "measured", hint: null },
  stampForecast: { word: "forecast", hint: null },
  stampHover: {
    word: "Numbers on this dashboard come from the measurement layer. A model's number is only ever a forecast, and the log rejects anything else at the gate.",
    hint: null,
  },
  provenanceTile: {
    word: "Numbers reported: {n} measured · {m} forecasts",
    hint: null,
  },
  provenanceCaption: {
    word: "0 exceptions possible — the gate refuses them.",
    hint: null,
  },
  memoryTitle: {
    word: "What the run has learned",
    hint: null,
  },
  memoryWeak: { word: "Weak spots", hint: null },
  memoryDirections: { word: "Promising directions", hint: null },
  memoryBanned: { word: "Banned patterns", hint: null },
  memorySeeded: {
    word: "known before the run started — the organisers' published dead ends",
    hint: null,
  },
  memoryVerbatimLead: {
    word: "This exact text is what the proposing model reads next round:",
    hint: null,
  },
  memoryEmpty: {
    word: "no failures yet — the run writes this page itself",
    hint: null,
  },
  claimMustUp: { word: "had to go up", hint: null },
  claimMustDown: { word: "had to go down", hint: null },
  claimMovedYes: { word: "yes", hint: null },
  claimMovedNo: { word: "no", hint: null },
  claimNotMeasured: { word: "not measured", hint: null },
  claimGiven: { word: "given", hint: null },
  claimRefused: { word: "refused", hint: null },
  claimTitle: { word: "Why we believe it", hint: null },
  claimRefusedSentence: {
    word: "Credit refused — the score moved but the stated mechanism's observables did not. This gain is not written into memory.",
    hint: null,
  },
  receiptFree: { word: "free checks", hint: "three free gates before any GPU is spent" },
  receiptSmoke: { word: "quick run", hint: null },
  receiptStopFree: {
    word: "Stopped at the free check — 0 model readings, 0 test runs spent.",
    hint: null,
  },
  receiptSemantic: {
    word: "all {n} judgment rules carried in one model reading",
    hint: null,
  },
  tourBriefTitle: { word: "Game plan", hint: null },
  tourBriefBody: {
    word: "This is what the agent was asked to do. Read it once, then look at the attempts.",
    hint: null,
  },
  tourRunTitle: { word: "Attempts tree", hint: null },
  tourRunBody: {
    word: "Every solution it tried, and the move that created each. Click an attempt to open its dossier.",
    hint: null,
  },
  tourJourneyTitle: { word: "One attempt's journey", hint: null },
  tourJourneyBody: {
    word: "Seven stages, including the free checks and the hidden check. Expand free checks to see the receipt.",
    hint: null,
  },
  tourMemoryTitle: { word: "What it learned", hint: null },
  tourMemoryBody: {
    word: "Weak spots, promising directions, and banned patterns. The footer is the exact text the proposing model reads next.",
    hint: null,
  },
  tourHeroTitle: { word: "The score", hint: null },
  tourHeroBody: {
    word: "The headline number, and whether to trust it. Stamps tell you if a figure was measured or only forecast.",
    hint: null,
  },
};

const STATE_LABELS = {
  screening: {
    word: "screening",
    hint: "running the quick test before a decision",
  },
  running: {
    word: "building",
    hint: "training is in progress",
  },
  replicating: {
    word: "repeating",
    hint: "running the repeat test",
  },
  promoted: DICT.promoted,
  inconclusive: DICT.inconclusive,
  rejected: DICT.rejected,
  retired: DICT.retired,
  leaked: DICT.leaked,
  debugging: {
    word: "fixing",
    hint: "repairing after a crash",
  },
  failed: DICT.failed,
};

export const BANNED = [
  "hypothesis",
  "hypotheses",
  "replicate",
  "oracle",
  "holdout",
  "rung",
  "verdict",
  "promoted",
  "inconclusive",
  "attribution",
  "incumbent",
  "v_sem",
  "leaked",
  "retired",
];

function passThrough(input) {
  return { word: String(input), hint: null };
}

export function stateLabel(state) {
  if (state == null) return passThrough(state);
  return STATE_LABELS[state] ?? passThrough(state);
}

export function moveLabel(kind) {
  if (kind == null) return { word: "—", hint: null };
  return DICT[kind] ?? passThrough(kind);
}

export function levelLabel(level) {
  if (level == null) return passThrough(level);
  return DICT[level] ?? passThrough(level);
}

export function rungLabel(rung) {
  if (rung == null) return passThrough(rung);
  return DICT[rung] ?? passThrough(rung);
}

export function attributionLabel(x) {
  return DICT[x]?.word ?? "unexplained";
}

export function claimLabel(level) {
  if (level == null) return passThrough(level);
  return DICT[level] ?? passThrough(level);
}

export function fmtScore(x) {
  if (x == null || (typeof x === "number" && Number.isNaN(x))) return "—";
  return Number(x).toFixed(4);
}

export function fmtDelta(x) {
  if (x == null || (typeof x === "number" && Number.isNaN(x))) return "—";
  const n = Number(x);
  const body = Math.abs(n).toFixed(4);
  if (n > 0) return `+${body}`;
  if (n < 0) return `-${body}`;
  return `+${body}`;
}

export function fmtTokens(n) {
  if (n == null || (typeof n === "number" && Number.isNaN(n))) return "—";
  if (n === 0) return "0";
  if (Math.abs(n) < 1000) return String(n);
  const k = n / 1000;
  const text = k.toFixed(1);
  return `${text}k`;
}

export function fmtDuration(s) {
  if (s == null || (typeof s === "number" && Number.isNaN(s))) return "—";
  const sec = Math.round(Number(s));
  const m = Math.floor(sec / 60);
  const r = Math.abs(sec % 60);
  if (m === 0) return `${r}s`;
  return `${m}m ${r}s`;
}
