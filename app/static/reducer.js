/** Checkpoint A: pure event reducer (no DOM). Contract: context/Handoff_app.md. */

// Mirrors harness/types.py. No Python at run time (purity rule below), so
// these are copied by hand — keep in sync if those tuples change.
const EVENT_TYPES = [
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
  "submission_written",
  "intervention",
  "run_ended",
];

const STATES = [
  "screening",
  "running",
  "replicating",
  "promoted",
  "inconclusive",
  "rejected",
  "retired",
  "leaked",
  "debugging",
];

// hypothesis_queued is named in neither the "feed includes" nor "feed
// excludes" list in Handoff_app.md's state contract. Treated as feed-worthy
// here — a new hypothesis is as discrete and significant as queue_reordered —
// pending confirmation from the doc owner.
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
]);

const LOG_CAP = 500;
const FEED_CAP = 50;
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
  interventions: [],

  log: [],
  feed: [],
  unknown: {},
});

function capPush(arr, item, cap) {
  return [...arr, item].slice(-cap);
}

function bump(map, key) {
  const k = key ?? "unspecified";
  return { ...map, [k]: (map[k] || 0) + 1 };
}

export function reduce(state, ev) {
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
        ruleTripsByRule: bump(state.reliability.ruleTripsByRule, ev.rule),
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
      break;
    }

    case "measurement": {
      next.measurements = capPush(state.measurements, ev, MEASUREMENTS_CAP);
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
