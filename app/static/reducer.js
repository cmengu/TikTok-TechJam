/** Phase 2: pure event reducer (no DOM). */

export const initial = () => ({
  run: null,
  nodes: {},
  queue: [],
  workers: {},
  verdicts: [],
  log: [],
  lastSeq: 0,
});

function appendScores(node, ev) {
  const scores = { ...node.scores };
  const metric = ev.metric;
  if (metric && Array.isArray(ev.scores)) {
    scores[metric] = [...(scores[metric] || []), ...ev.scores];
  }
  const seeds = Array.isArray(ev.seeds)
    ? [...node.seeds, ...ev.seeds]
    : [...node.seeds];
  return { ...node, scores, seeds };
}

export function reduce(state, ev) {
  const next = {
    ...state,
    nodes: { ...state.nodes },
    queue: [...state.queue],
    workers: { ...state.workers },
    verdicts: [...state.verdicts],
    log: [...state.log, ev].slice(-200),
    lastSeq: ev.seq,
  };

  switch (ev.type) {
    case "run_started": {
      const protocol = ev.protocol || {};
      next.run = {
        id: ev.run,
        protocol_hash: ev.protocol_hash,
        task: protocol.task,
      };
      break;
    }
    case "node_created": {
      next.nodes[ev.id] = {
        id: ev.id,
        parent: ev.parent ?? null,
        state: "screening",
        kind: ev.kind,
        scores: {},
        seeds: [],
      };
      break;
    }
    case "state_changed": {
      const id = ev.node;
      const cur = next.nodes[id];
      if (cur) next.nodes[id] = { ...cur, state: ev.state };
      break;
    }
    case "hypothesis_queued": {
      next.queue.push({ ...ev });
      break;
    }
    case "queue_reordered": {
      const byId = new Map(next.queue.map((h) => [h.id, h]));
      next.queue = (ev.order || []).map((id) => byId.get(id)).filter(Boolean);
      break;
    }
    case "heartbeat": {
      next.workers[ev.worker] = ev;
      break;
    }
    case "verdict": {
      next.verdicts.push(ev);
      const id = ev.node;
      const cur = next.nodes[id];
      if (cur) {
        next.nodes[id] = { ...appendScores(cur, ev), state: ev.state };
      }
      break;
    }
    default:
      break;
  }
  return next;
}
