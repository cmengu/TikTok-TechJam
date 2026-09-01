/** LuxMax event feed sentences — pure, never throws. */

import {
  fmtDelta,
  fmtScore,
  levelLabel,
  moveLabel,
  stateLabel,
} from "./copy.js";
import { moveTargets } from "./tree.js";

export function sentence(ev) {
  try {
    if (ev == null || typeof ev !== "object") {
      return String(ev ?? "");
    }
    const node = ev.node ?? "?";
    const type = ev.type;

    if (type === "verdict") return verdictSentence(ev, node);
    if (type === "move_selected") return moveSentence(ev);
    if (type === "proposal_rejected") {
      const pattern = ev.pattern ?? "?";
      return `Idea declined for free — '${pattern}' is banned.`;
    }
    if (type === "verify_level") {
      const level = levelLabel(ev.level).word;
      if (ev.passed) return `Attempt ${node} passed the ${level} check.`;
      return `Attempt ${node} failed the ${level} check.`;
    }
    if (type === "failure") {
      const cls = ev.class ? `: ${ev.class}` : "";
      return `Attempt ${node} crashed${cls}.`;
    }
    if (type === "recovery") {
      return `Attempt ${node} recovered.`;
    }
    if (type === "rule_trip") {
      const rule = ev.rule_id ?? ev.rule ?? "?";
      if (ev.level != null) {
        return `Attempt ${node} tripped ${rule} on the ${levelLabel(ev.level).word} check.`;
      }
      return `Attempt ${node} tripped ${rule}.`;
    }
    if (type === "attribution_checked") {
      if (ev.result === "clear") {
        return `Attempt ${node} win is explained.`;
      }
      if (ev.result === "unclear") {
        return `Attempt ${node} win is unexplained.`;
      }
      return `Attempt ${node} win check finished.`;
    }
    if (type === "incumbent_changed") {
      return `Attempt ${node} is the current best.`;
    }
    if (type === "submission_written") {
      return `Submission written from attempt ${node}.`;
    }
    if (type === "submission_run") {
      return `Submission run for attempt ${node}.`;
    }
    if (type === "measurement") {
      return measurementSentence(ev, node);
    }
    if (type === "hypothesis_queued") {
      const id = ev.id ?? "?";
      return `Idea ${id} queued.`;
    }
    if (type === "lesson_written") {
      return `Note written for attempt ${node}.`;
    }
    if (type === "research_source") {
      const title = ev.title ?? "a paper";
      return `Paper read: ${title}.`;
    }
    if (type === "node_created") {
      return `Attempt ${ev.id ?? node} built.`;
    }
    if (type === "state_changed") {
      return `Attempt ${node} ${stateLabel(ev.state).word}.`;
    }
    if (type === "run_started") {
      return "Run started.";
    }
    if (type === "run_ended") {
      return "Run ended.";
    }
    if (type === "prediction") {
      return `Hidden check scored for attempt ${node}.`;
    }
    if (type === "cache_lookup") {
      return ev.hit ? "Paper cache hit." : "Paper cache miss.";
    }
    if (type === "queue_reordered") {
      return "Idea queue reordered.";
    }
    if (type === "intervention") {
      return "Operator intervened.";
    }
    // Last resort: never echo harness summary bytes (they carry banned jargon).
    return type ? String(type).replaceAll("_", " ") : "";
  } catch {
    try {
      return String(ev?.type || "");
    } catch {
      return "";
    }
  }
}

function measurementSentence(ev, node) {
  const metric = ev.metric ?? "score";
  const value = ev.value != null ? fmtScore(ev.value) : null;
  if (ev.split === "holdout" || ev.visit != null) {
    const visit = ev.visit != null ? ` #${ev.visit}` : "";
    return value != null
      ? `Hidden check${visit}: ${value}.`
      : `Hidden check${visit}.`;
  }
  const seed = ev.seed != null ? ` seed ${ev.seed}` : "";
  return value != null
    ? `Attempt ${node}${seed}: ${metric} ${value}.`
    : `Attempt ${node} measured.`;
}

function verdictSentence(ev, node) {
  const state = ev.state;
  const attribution = ev.attribution;
  const oracle = ev.oracle_delta;

  if (state === "promoted") {
    if (oracle != null) {
      return `Attempt ${node} accepted — repeat test passed, confirmed on the hidden check (${fmtDelta(oracle)}).`;
    }
    return `Attempt ${node} accepted.`;
  }
  if (attribution === "unclear") {
    return `Attempt ${node} passed the tests, but the win is unexplained — not accepted.`;
  }
  if (state === "rejected") {
    return `Attempt ${node} declined.`;
  }
  if (state === "inconclusive") {
    return `Attempt ${node} retrying.`;
  }
  if (state === "replicating") {
    return `Attempt ${node} repeating.`;
  }
  if (state == null) {
    return `Attempt ${node} accepted.`;
  }
  return `Attempt ${node} ${stateLabel(state).word}.`;
}

function moveSentence(ev) {
  const kind = moveLabel(ev.kind);
  const reason = ev.reason ? ` — ${ev.reason}` : "";
  if (ev.kind === "improve" && ev.parent != null) {
    return `Next move: build on attempt ${ev.parent}${reason}.`;
  }
  return `Next move: ${kind.word}${reason}.`;
}

/** D4 — moves in order with optional attempt links. Newest last. */
export function buildMoveTrail(state) {
  return moveTargets(state).map(({ move, nodeId }) => ({
    text: sentence(move),
    href:
      nodeId != null && String(nodeId) !== "null" && String(nodeId) !== "undefined"
        ? `#/run/${nodeId}`
        : null,
  }));
}
