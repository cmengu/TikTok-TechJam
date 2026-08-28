/** Checkpoint 1: pure band/verdict reader (no DOM, no app.js imports). Contract: harness/measure.py Band + screen_verdict/promote_bar. */

// Mirrors harness/measure.py:19 — Redline §6 Ladder: screen — delta ≥ this ×
// sd_delta_screen → replicating. Copied by hand — keep in sync.
export const SCREEN_ADVANCE_SD = 1.0;

// Mirrors harness/measure.py:51-61 (class Band, dataclass field order):
//   sigma_screen: float
//   sigma_full: float
//   sigma_pair: float
//   ratio: float
//   rho: float
//   sd_delta_screen: float
//   sd_delta_full: float
//   bar: float
//   source: Literal["fixed_pair", "refreshed"]
//   n_replicated: int
export const BAND_FIELDS = [
  "sigma_screen",
  "sigma_full",
  "sigma_pair",
  "ratio",
  "rho",
  "sd_delta_screen",
  "sd_delta_full",
  "bar",
  "source",
  "n_replicated",
];

function isFiniteNumber(x) {
  return typeof x === "number" && Number.isFinite(x);
}

function mean(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

// raw is a verdict/prediction event's "band" field, which comes in one of
// two shapes depending on where it was emitted:
//   - harness/measure.py:432 (`"band": _band_payload(band)`) and :513
//     (`band=_band_payload(self.band) if self.band else None`) — an
//     asdict(Band) object, all BAND_FIELDS keys.
//   - harness/fake_run.py's demo script — a plain [lo, hi] two-tuple (see
//     app.js:110-111), unchanged, still what most committed fixtures carry.
// Never throws, never coerces one shape into the other.
export function readBand(raw) {
  if (Array.isArray(raw)) {
    if (raw.length === 2 && isFiniteNumber(raw[0]) && isFiniteNumber(raw[1])) {
      return { shape: "legacy", fields: { lo: raw[0], hi: raw[1] } };
    }
    return { shape: "none", fields: null };
  }
  if (raw !== null && typeof raw === "object") {
    return { shape: "measure", fields: raw };
  }
  return { shape: "none", fields: null };
}

export function verdictReading(verdict) {
  const raw = verdict ? verdict.band : undefined;
  const { shape, fields } = readBand(raw);

  let value = null;
  let valueKind = null;
  if (verdict && isFiniteNumber(verdict.delta_mean)) {
    value = verdict.delta_mean;
    valueKind = "delta";
  } else if (verdict && Array.isArray(verdict.scores) && verdict.scores.length) {
    value = mean(verdict.scores);
    valueKind = "score";
  }

  // harness/measure.py:417 (`rung=rung,`) and :433 (`"rung": rung,`) put the
  // rung that actually produced this verdict straight into the payload —
  // read it, don't re-derive it from state. A dict band with no rung (e.g.
  // fake_run.py's demo verdicts) means "I don't know which comparison the
  // harness made", not a guess: threshold/thresholdLabel stay null.
  const rung = verdict ? (verdict.rung ?? null) : null;

  let threshold = null;
  let thresholdLabel = null;
  if (shape === "measure") {
    if (rung === "screen" && isFiniteNumber(fields.sd_delta_screen)) {
      // harness/measure.py:194 (screen_verdict):
      //   if delta >= SCREEN_ADVANCE_SD * band.sd_delta_screen:
      threshold = SCREEN_ADVANCE_SD * fields.sd_delta_screen;
      thresholdLabel = "sd_delta_screen";
    } else if (rung === "replicate" && isFiniteNumber(fields.bar)) {
      // harness/measure.py:199-200 (promote_bar):
      //   def promote_bar(band: Band) -> float:
      //       return _bar_from(band.sd_delta_full)
      // band.bar (the payload field, per class Band:59 `bar: float`) is that
      // same precomputed value — read it directly rather than recomputing.
      threshold = fields.bar;
      thresholdLabel = "bar";
    }
  }
  // shape "legacy" or "none": threshold stays null. lo/hi are not a
  // threshold the harness compared against — fabricating one from them
  // would misrepresent what screen_verdict/promote_bar actually did.

  // harness/measure.py:194 (screen_verdict): `if delta >= SCREEN_ADVANCE_SD * band.sd_delta_screen:`
  //   advances on >=, so a delta exactly at the threshold passes.
  // harness/measure.py:214 (replicate_verdict): `if statistics.mean(values) < promote_bar(band):`
  //   fails on <, so a mean exactly at the bar also passes.
  // Either way "at" falls on the passing side — this is recorded here, not
  // changed: side below still reports "at" as its own value, not "above".
  let side = null;
  if (value != null && threshold != null) {
    if (value > threshold) side = "above";
    else if (value < threshold) side = "below";
    else side = "at";
  }

  return { shape, value, valueKind, threshold, thresholdLabel, side, rung };
}

function fmtNum(n) {
  return Number(n.toFixed(6)).toString();
}

// Handoff_app.md, "The band contract — settled, do not re-litigate", rule 2:
//   "A missing rung is not a guess. A dict band with no `rung` means "we
//    do not know which comparison the harness made". `threshold` stays null.
//    Same rule as spend and vs-baseline significance: a visible gap beats a
//    plausible number."
// rule 3:
//   "`legacy` and `none` never get a threshold. `lo`/`hi` are not
//    something `screen_verdict` or `promote_bar` compared against."
// verdictAnnotation never fabricates a comparison for the cases those rules
// forbid one for — it names the gap instead.
export function verdictAnnotation(verdict) {
  const { shape, value, threshold, thresholdLabel, side, rung } = verdictReading(verdict);

  if (threshold != null && value != null) {
    const sign = value < 0 ? "-" : "+";
    const symbol = side === "below" ? "<" : "≥";
    return {
      text: `Δ ${sign}${fmtNum(Math.abs(value))} ${symbol} ${thresholdLabel} ${fmtNum(threshold)}`,
      reason: null,
    };
  }

  if (shape === "legacy") {
    return {
      text: null,
      reason:
        "band is fake_run.py's legacy lo/hi pair — the harness reported no threshold this verdict was tested against",
    };
  }

  if (shape === "measure") {
    return {
      text: null,
      reason:
        rung == null
          ? "verdict carries no rung — which comparison the harness made is unknown"
          : "the harness's threshold for this comparison is unavailable",
    };
  }

  return { text: null, reason: "no band was reported for this verdict" };
}
