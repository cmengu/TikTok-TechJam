/** Checkpoint A: pure event reducer (no DOM). Contract: context/Handoff_app.md. */

// Mirrors harness/types.py. No Python at run time (purity rule below), so
// these are copied by hand — keep in sync if those tuples change.
export const EVENT_TYPES = [
  "run_started",
  "node_created",
  "state_changed",
  "heartbeat",
  "measurement",
  "verdict",
  "failure",
  "recovery",
  "rule_trip",
  "research_source",
  "cache_lookup",
  "hypothesis_queued",
  "queue_reordered",
  "submission_run",
  "submission_written",
  "intervention",
  "run_ended",
  // Phase 5 (Plan_delta §1: additive types, no schema bump) — mirrors
  // harness/types.py EVENT_TYPES.
  "incumbent_changed",
  "prediction",
  // Phase 2 (context/Phase2_event_contract.md: additive types, no schema bump)
  // — mirrors harness/types.py EVENT_TYPES.
  "lesson_written",
  "proposal_rejected",
  "attribution_checked",
  "move_selected",
  "verify_level",
];

export const STATES = [
  "screening",
  "running",
  "replicating",
  "promoted",
  "inconclusive",
  "rejected",
  "retired",
  "leaked",
  "debugging",
  // Phase 2 step 11b: a crash or contract violation parks the node here until
  // a debug move repairs it or DEBUG_DEPTH retires it.
  "failed",
];

// hypothesis_queued is feed-worthy: a new hypothesis is the only visible
// output of the researcher agent, and Innovation is judged on what the agent
// chose to try. (Startup bursts are a rendering concern — collapse
// consecutive same-type rows in the view — not a reducer concern.)
const FEED_TYPES = new Set([
  "run_started",
  "node_created",
  "state_changed",
  "verdict",
  "failure",
  "recovery",
  "rule_trip",
  "hypothesis_queued",
  "queue_reordered",
  "submission_written",
  "intervention",
  "run_ended",
  // Both are rare, milestone-like events (not high-frequency ticks like
  // measurement/cache_lookup): incumbent_changed only fires on promotion,
  // prediction only fires up to HOLDOUT_VISITS_MAX (=2) times per run
  // (harness/measure.py:33).
  "incumbent_changed",
  "prediction",
  // Phase 2: each marks a stage of one round — a gate decision, a lesson, an
  // attribution, a topology move. None is a high-frequency tick.
  "submission_run",
  "lesson_written",
  "proposal_rejected",
  "attribution_checked",
  "move_selected",
  "verify_level",
]);

const LOG_CAP = 500;
const FEED_CAP = 1000;
const MEASUREMENTS_CAP = 500;

export const initial = () => ({
  lastSeq: 0,
  lastHeartbeatSeq: 0,

  run: {
    id: null,
    task: null,
    protocolHash: null,
    protocol: null,
    startedAt: null,
    endedAt: null,
    endReason: null,
    status: "waiting",
  },

  nodes: {},
  nodeOrder: [],

  queue: [],

  workers: {},

  verdicts: [],
  measurements: [],
  predictions: [],
  incumbentChanges: [],
  incumbent: null, // current incumbent node id; null until the first promotion

  research: {
    sources: [],
    lookups: [],
    hits: 0,
    misses: 0,
    confirmed: 0,
    contradicted: 0,
  },

  reliability: {
    failures: [],
    recoveries: [],
    ruleTrips: [],
    failuresByClass: {},
    recoveriesByClass: {},
    ruleTripsByRule: {},
  },

  submissions: [],
  submissionRuns: [],
  interventions: [],

  // --- Phase 2 (context/Phase2_event_contract.md) ---------------------------
  /** move_selected, in order: the topology decision taken each round. */
  moves: [],
  /**
   * The verification cascade. `byNode[id]` is that node's level history;
   * `rejected` counts where a node died, so "rejected for free" (omega, before
   * any LLM call or run) is a number on screen; `counters` totals what the
   * cascade actually spent.
   */
  cascade: {
    byNode: {},
    rejected: { omega: 0, v_sem: 0, smoke: 0 },
    counters: { llmCalls: 0, runs: 0 },
  },
  /** lesson_written rows, same shape as lessons.jsonl. */
  lessons: [],
  /** proposal_rejected keyed by pattern — the forbidden set, first sighting wins. */
  forbidden: {},
  /** attribution_checked keyed by node — the observables behind clear/unclear. */
  attribution: { byNode: {} },

  /** Current incumbent node id (null until first promotion / incumbent_changed). */
  incumbent: null,

  log: [],
  feed: [],
  unknown: {},
});

function capPush(arr, item, cap) {
  return [...arr, item].slice(-cap);
}

function isNum(x) {
  return typeof x === "number" && Number.isFinite(x);
}

function numOr0(x) {
  return isNum(x) ? x : 0;
}

function bump(map, key) {
  const k = key ?? "unspecified";
  return { ...map, [k]: (map[k] || 0) + 1 };
}

export function reduce(state, ev) {
  // Per-stream duplicate guard: events.jsonl and heartbeat.jsonl each have
  // their own seq counter, so a replay or an overlapping ?since= page must be
  // checked against the matching cursor, not a shared one.
  if (ev.type === "heartbeat" && ev.seq <= state.lastHeartbeatSeq) return state;
  if (ev.type !== "heartbeat" && ev.seq <= state.lastSeq) return state;

  if (ev.type === "heartbeat") {
    // Independent seq counter from events.jsonl (EventLog._heartbeat_seq vs
    // _event_seq) — must never touch lastSeq, and never enters log/feed.
    return {
      ...state,
      lastHeartbeatSeq: ev.seq,
      workers: { ...state.workers, [ev.worker]: ev },
    };
  }

  let next = { ...state, lastSeq: ev.seq };

  if (!EVENT_TYPES.includes(ev.type)) {
    return {
      ...next,
      unknown: bump(next.unknown, ev.type),
      log: capPush(next.log, ev, LOG_CAP),
    };
  }

  switch (ev.type) {
    case "run_started": {
      const protocol = ev.protocol ?? null;
      next.run = {
        ...state.run,
        id: ev.run,
        task: protocol ? protocol.task : state.run.task,
        protocolHash: ev.protocol_hash,
        protocol,
        startedAt: ev.t,
        status: "running",
      };
      break;
    }

    case "node_created": {
      const hypothesisId = ev.hypothesis_id ?? null;
      const node = {
        id: ev.id,
        parent: ev.parent ?? null,
        kind: ev.kind,
        hypothesisId,
        state: "screening",
        stateHistory: [{ state: "screening", seq: ev.seq, t: ev.t }],
        scores: {},
        seeds: [],
        bands: {},
        latestVerdict: null,
        failures: [],
        recoveries: [],
        ruleTrips: [],
        createdSeq: ev.seq,
      };
      next.nodes = { ...state.nodes, [node.id]: node };
      next.nodeOrder = [...state.nodeOrder, node.id];
      if (hypothesisId != null) {
        next.queue = state.queue.map((q) =>
          q.id === hypothesisId ? { ...q, nodeId: node.id, started: true } : q,
        );
      }
      break;
    }

    case "state_changed": {
      if (!STATES.includes(ev.state)) {
        next.unknown = bump(next.unknown, `state:${ev.state}`);
        break;
      }
      const cur = state.nodes[ev.node];
      if (cur) {
        next.nodes = {
          ...state.nodes,
          [ev.node]: {
            ...cur,
            state: ev.state,
            stateHistory: [
              ...cur.stateHistory,
              { state: ev.state, seq: ev.seq, t: ev.t },
            ],
          },
        };
      }
      break;
    }

    case "verdict": {
      next.verdicts = [...state.verdicts, ev];
      const cur = state.nodes[ev.node];
      if (cur) {
        let node = cur;
        if (ev.metric && Array.isArray(ev.scores)) {
          node = {
            ...node,
            scores: {
              ...node.scores,
              [ev.metric]: [...(node.scores[ev.metric] || []), ...ev.scores],
            },
          };
        }
        if (Array.isArray(ev.seeds)) {
          node = { ...node, seeds: [...node.seeds, ...ev.seeds] };
        }
        if (ev.metric && ev.band) {
          node = { ...node, bands: { ...node.bands, [ev.metric]: ev.band } };
        }
        node = { ...node, latestVerdict: ev };
        if (ev.state != null) {
          if (STATES.includes(ev.state)) {
            node = {
              ...node,
              state: ev.state,
              stateHistory: [
                ...node.stateHistory,
                { state: ev.state, seq: ev.seq, t: ev.t },
              ],
            };
          } else {
            next.unknown = bump(next.unknown, `state:${ev.state}`);
          }
        }
        next.nodes = { ...state.nodes, [ev.node]: node };
      }
      break;
    }

    case "failure": {
      next.reliability = {
        ...state.reliability,
        failures: [...state.reliability.failures, ev],
        failuresByClass: bump(state.reliability.failuresByClass, ev.class),
      };
      const cur = state.nodes[ev.node];
      if (cur) {
        next.nodes = {
          ...state.nodes,
          [ev.node]: { ...cur, failures: [...cur.failures, ev] },
        };
      }
      break;
    }

    case "recovery": {
      next.reliability = {
        ...state.reliability,
        recoveries: [...state.reliability.recoveries, ev],
        recoveriesByClass: bump(state.reliability.recoveriesByClass, ev.class),
      };
      const cur = state.nodes[ev.node];
      if (cur) {
        next.nodes = {
          ...state.nodes,
          [ev.node]: { ...cur, recoveries: [...cur.recoveries, ev] },
        };
      }
      break;
    }

    case "rule_trip": {
      next.reliability = {
        ...state.reliability,
        ruleTrips: [...state.reliability.ruleTrips, ev],
        // Phase 2 renamed the field to `rule_id` (event contract). Older
        // emitters (measure.py leak audit, tree.py duplicate hypothesis) still
        // send `rule`; accept both rather than bucketing half as "unspecified".
        ruleTripsByRule: bump(
          state.reliability.ruleTripsByRule,
          ev.rule_id ?? ev.rule,
        ),
      };
      if (ev.node != null) {
        const cur = state.nodes[ev.node];
        if (cur) {
          next.nodes = {
            ...state.nodes,
            [ev.node]: { ...cur, ruleTrips: [...cur.ruleTrips, ev] },
          };
        }
      }
      break;
    }

    case "research_source": {
      const idx = state.research.sources.findIndex((s) => s.id === ev.id);
      const sources =
        idx === -1
          ? [...state.research.sources, ev]
          : state.research.sources.map((s, i) => (i === idx ? ev : s));
      next.research = { ...state.research, sources };
      break;
    }

    case "cache_lookup": {
      const hit = ev.hit === true;
      let confirmed = state.research.confirmed;
      let contradicted = state.research.contradicted;
      if (ev.confirmed === true) confirmed += 1;
      else if (ev.confirmed === false) contradicted += 1;
      next.research = {
        ...state.research,
        lookups: [...state.research.lookups, ev],
        hits: state.research.hits + (hit ? 1 : 0),
        misses: state.research.misses + (hit ? 0 : 1),
        confirmed,
        contradicted,
      };
      break;
    }

    case "hypothesis_queued": {
      const entry = {
        id: ev.id,
        stage: ev.stage,
        mechanism: ev.mechanism,
        parentNode: ev.parent_node ?? null,
        position: state.queue.length,
        prevPosition: null,
        movement: 0,
        queuedSeq: ev.seq,
        nodeId: null,
        started: false,
      };
      next.queue = [...state.queue, entry];
      break;
    }

    case "queue_reordered": {
      // Bug fix: entries absent from ev.order must keep their relative order
      // and be appended after the named ones, not be dropped.
      const order = Array.isArray(ev.order) ? ev.order : [];
      const byId = new Map(state.queue.map((q) => [q.id, q]));
      const namedIds = new Set();
      const named = [];
      for (const id of order) {
        const q = byId.get(id);
        if (q && !namedIds.has(id)) {
          named.push(q);
          namedIds.add(id);
        }
      }
      const unnamed = state.queue.filter((q) => !namedIds.has(q.id));
      next.queue = [...named, ...unnamed].map((q, i) => ({
        ...q,
        prevPosition: q.position,
        position: i,
        movement: q.position - i,
      }));
      break;
    }

    case "submission_written": {
      next.submissions = [...state.submissions, ev];
      break;
    }

    case "intervention": {
      next.interventions = [...state.interventions, ev];
      break;
    }

    case "run_ended": {
      next.run = {
        ...state.run,
        endedAt: ev.t,
        endReason: ev.reason,
        status: "ended",
      };
      if (ev.incumbent != null) {
        next.incumbent = ev.incumbent;
      }
      break;
    }

    // --- Phase 2 -------------------------------------------------------------
    // Each case skips an event missing its identifying field rather than
    // throwing: a malformed line must never take the stream down.

    case "submission_run": {
      if (!isNum(ev.node)) {
        next.unknown = bump(next.unknown, "malformed:submission_run");
        break;
      }
      next.submissionRuns = capPush(state.submissionRuns, ev, LOG_CAP);
      break;
    }

    case "move_selected": {
      if (!isNum(ev.round)) {
        next.unknown = bump(next.unknown, "malformed:move_selected");
        break;
      }
      next.moves = capPush(state.moves, ev, LOG_CAP);
      break;
    }

    case "verify_level": {
      if (!isNum(ev.node) || typeof ev.level !== "string") {
        next.unknown = bump(next.unknown, "malformed:verify_level");
        break;
      }
      const prior = state.cascade.byNode[ev.node] || [];
      const rejected = { ...state.cascade.rejected };
      // `passed === false` is the only rejection; a missing flag is not one.
      if (ev.passed === false && rejected[ev.level] !== undefined) {
        rejected[ev.level] = rejected[ev.level] + 1;
      }
      next.cascade = {
        ...state.cascade,
        byNode: { ...state.cascade.byNode, [ev.node]: [...prior, ev] },
        rejected,
        counters: {
          llmCalls: state.cascade.counters.llmCalls + numOr0(ev.llm_calls),
          runs: state.cascade.counters.runs + numOr0(ev.runs),
        },
      };
      break;
    }

    case "lesson_written": {
      if (!isNum(ev.node)) {
        next.unknown = bump(next.unknown, "malformed:lesson_written");
        break;
      }
      next.lessons = capPush(state.lessons, ev, LOG_CAP);
      break;
    }

    case "proposal_rejected": {
      if (typeof ev.pattern !== "string" || ev.pattern === "") {
        next.unknown = bump(next.unknown, "malformed:proposal_rejected");
        break;
      }
      // First sighting wins: `first_round` is the round the pattern was banned,
      // and a later rejection must not overwrite it.
      next.forbidden = state.forbidden[ev.pattern]
        ? state.forbidden
        : { ...state.forbidden, [ev.pattern]: ev };
      break;
    }

    case "attribution_checked": {
      if (!isNum(ev.node) || typeof ev.result !== "string") {
        next.unknown = bump(next.unknown, "malformed:attribution_checked");
        break;
      }
      next.attribution = {
        ...state.attribution,
        byNode: { ...state.attribution.byNode, [ev.node]: ev },
      };
      break;
    }

    case "measurement": {
      next.measurements = capPush(state.measurements, ev, MEASUREMENTS_CAP);
      break;
    }

    // Emitted by harness/measure.py:445-450:
    //   self.events.emit("incumbent_changed", node=node.id, reason="promotion",
    //                     summary=f"node {node.id} became incumbent (promotion)")
    // Proven fields: node, reason, summary. Stored whole (same convention as
    // verdict/submission_written/intervention below) — no field invented.
    case "incumbent_changed": {
      next.incumbentChanges = [...state.incumbentChanges, ev];
      next.incumbent = ev.node ?? state.incumbent;
      break;
    }

    // Emitted by harness/measure.py:507-515:
    //   self.events.emit("prediction", node=node.id, metric=METRIC, value=new_holdout,
    //                     best_reported=next_best, band=_band_payload(self.band) if self.band else None,
    //                     summary=f"prediction {new_holdout:.4f} (η ladder accepted)")
    // Proven fields: node, metric, value, best_reported, band, summary. Only
    // fires up to HOLDOUT_VISITS_MAX (=2) times per run, so plain (uncapped)
    // push mirrors verdicts/submissions rather than the capPush used for the
    // high-frequency "measurement" ticks.
    case "prediction": {
      next.predictions = [...state.predictions, ev];
      break;
    }

    default:
      break;
  }

  next.log = capPush(next.log, ev, LOG_CAP);
  if (FEED_TYPES.has(ev.type)) {
    next.feed = capPush(next.feed, ev, FEED_CAP);
  }
  return next;
}
