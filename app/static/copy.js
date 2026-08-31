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
