/** F1 — counts fold. Every value is a COUNT OF EVENTS. Pure: no DOM, no fetch. */

export const TRACE_KEYS = [
  "papersRead",
  "ideasProposed",
  "ideasBanned",
  "attemptsBuilt",
  "quickTests",
  "repeatTests",
  "hiddenChecks",
  "accepted",
  "declined",
  "retrying",
  "shelved",
  "crashed",
];

function zeros() {
  return Object.fromEntries(TRACE_KEYS.map((k) => [k, 0]));
}

// Fix-list item 1: harness/agents/llm.py logs cost bookkeeping after every
// LLM call as a research_source titled "llm usage" (riding the paper event
// type so the cost field attaches). Those rows are spend, not reading —
// frontend folds skip them; the emission itself stays untouched
// (additive-events law).
export function isCostBookkeeping(ev) {
  return ev?.type === "research_source" && ev?.title === "llm usage";
}

/**
 * buildTrace(state) → counts of events on state.log.
 *
 * quickTests / repeatTests count verdict events by rung, not unique nodes —
 * two screen verdicts on one attempt are two quick tests. hiddenChecks counts
 * measurement events with rung holdout|oracle (the hidden-check visit), not
 * oracle_delta fields hanging on a verdict. crashed counts failure events.
 */
export function buildTrace(state) {
  const out = zeros();
  const events = Array.isArray(state?.log) ? state.log : [];
  for (const ev of events) {
    if (ev == null || typeof ev !== "object") continue;
    switch (ev.type) {
      case "research_source":
        if (!isCostBookkeeping(ev)) out.papersRead += 1;
        break;
      case "hypothesis_queued":
        out.ideasProposed += 1;
        break;
      case "proposal_rejected":
        out.ideasBanned += 1;
        break;
      case "node_created":
        out.attemptsBuilt += 1;
        break;
      case "verdict":
        if (ev.rung === "screen") out.quickTests += 1;
        if (ev.rung === "replicate") out.repeatTests += 1;
        if (ev.state === "promoted") out.accepted += 1;
        if (ev.state === "rejected") out.declined += 1;
        if (ev.state === "inconclusive") out.retrying += 1;
        if (ev.state === "retired") out.shelved += 1;
        break;
      case "measurement":
        if (ev.rung === "holdout" || ev.rung === "oracle") out.hiddenChecks += 1;
        break;
      case "failure":
        out.crashed += 1;
        break;
      default:
        break;
    }
  }
  return out;
}
