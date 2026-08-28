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

// Same state split as app.js:118-122's verdictBandTest, duplicated (not
// moved — band.js may not import from app.js):
//   function verdictBandTest(state) {
//     if (state === "inconclusive" || state === "rejected") return "screening";
//     if (state === "replicating" || state === "promoted") return "replication";
//     return null;
//   }
// app.js's own comment there notes this state-based split doesn't perfectly
// track which harness function (screen_verdict vs replicate_verdict)
// actually produced the state — that ambiguity is inherited here as-is.
function verdictBandTest(state) {
  if (state === "inconclusive" || state === "rejected") return "screening";
  if (state === "replicating" || state === "promoted") return "replication";
  return null;
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

  let threshold = null;
  let thresholdLabel = null;
  if (shape === "measure") {
    const split = verdict ? verdictBandTest(verdict.state) : null;
    if (split === "screening" && isFiniteNumber(fields.sd_delta_screen)) {
      // harness/measure.py:194 (screen_verdict):
      //   if delta >= SCREEN_ADVANCE_SD * band.sd_delta_screen:
      threshold = SCREEN_ADVANCE_SD * fields.sd_delta_screen;
      thresholdLabel = "sd_delta_screen";
    } else if (split === "replication" && isFiniteNumber(fields.bar)) {
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

  let side = null;
  if (value != null && threshold != null) {
    if (value > threshold) side = "above";
    else if (value < threshold) side = "below";
    else side = "at";
  }

  return { shape, value, valueKind, threshold, thresholdLabel, side };
}
