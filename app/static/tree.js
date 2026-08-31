/** Checkpoint 2 + D3: pure flat-node-map -> nested tree reader (no DOM). */

import { moveLabel, stateLabel } from "./copy.js";
import { buildJourney } from "./journey.js";

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function createdSeqOf(node) {
  return node && Number.isFinite(node.createdSeq) ? node.createdSeq : 0;
}

function hasNode(nodes, id) {
  return (
    id !== null &&
    id !== undefined &&
    Object.prototype.hasOwnProperty.call(nodes, id) &&
    isPlainObject(nodes[id])
  );
}

function bestPathSet(state) {
  const set = new Set();
  const nodes = state?.nodes;
  if (!isPlainObject(nodes) || state.incumbent == null) return set;
  let id = state.incumbent;
  const guard = new Set();
  while (id != null && hasNode(nodes, id) && !guard.has(String(id))) {
    set.add(String(id));
    guard.add(String(id));
    id = nodes[id].parent;
  }
  return set;
}

/** Seq-sorted: each node_created takes the immediately preceding move_selected. */
function edgeLabelMap(state) {
  const labels = new Map();
  const nodes = state?.nodes;
  if (!isPlainObject(nodes)) return labels;

  const moves = Array.isArray(state.moves) ? state.moves : [];
  const creations = [];
  for (const key of Object.keys(nodes)) {
    const n = nodes[key];
    if (!isPlainObject(n)) continue;
    creations.push({
      seq: createdSeqOf(n),
      id: n.id ?? key,
      type: "node_created",
    });
  }
  const timeline = [
    ...moves.map((m) => ({
      seq: Number.isFinite(m.seq) ? m.seq : 0,
      type: "move_selected",
      move: m,
    })),
    ...creations,
  ].sort((a, b) => a.seq - b.seq || (a.type === "move_selected" ? -1 : 1));

  let lastMove = null;
  for (const item of timeline) {
    if (item.type === "move_selected") {
      lastMove = item.move;
    } else {
      labels.set(
        String(item.id),
        lastMove != null ? moveLabel(lastMove.kind).word : null,
      );
      lastMove = null;
    }
  }
  return labels;
}

function enrich(entry, state, pathSet, edges) {
  const node = entry.node;
  const id = String(node.id);
  const journey = buildJourney(state, node.id);
  entry.plainState = stateLabel(node.state);
  entry.onBestPath = pathSet.has(id);
  entry.dimmed = ["rejected", "retired", "leaked"].includes(node.state);
  entry.loops = journey ? journey.loops : 0;
  entry.edgeLabel = edges.has(id) ? edges.get(id) : null;
  for (const child of entry.children) enrich(child, state, pathSet, edges);
  return entry;
}

/**
 * moveTargets(state) → [{ move, nodeId }] in move order.
 * nodeId is the attempt produced by the immediately following node_created, or null.
 */
export function moveTargets(state) {
  const moves = Array.isArray(state?.moves) ? state.moves : [];
  const nodes = state?.nodes;
  if (!isPlainObject(nodes)) {
    return moves.map((move) => ({ move, nodeId: null }));
  }

  const creations = Object.keys(nodes)
    .map((key) => {
      const n = nodes[key];
      return isPlainObject(n)
        ? { seq: createdSeqOf(n), id: n.id ?? key }
        : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.seq - b.seq);

  const sortedMoves = [...moves].sort(
    (a, b) => (a.seq ?? 0) - (b.seq ?? 0),
  );
  const used = new Set();
  return sortedMoves.map((move) => {
    const next = creations.find(
      (c) => c.seq > (move.seq ?? 0) && !used.has(String(c.id)),
    );
    if (!next) return { move, nodeId: null };
    // Ensure no other move sits between this move and the creation.
    const intervening = sortedMoves.some(
      (m) =>
        m !== move &&
        (m.seq ?? 0) > (move.seq ?? 0) &&
        (m.seq ?? 0) < next.seq,
    );
    if (intervening) return { move, nodeId: null };
    used.add(String(next.id));
    return { move, nodeId: next.id };
  });
}

// buildTree(state) -> array of root nodes, each { node, children, orphan, …D3 }.
export function buildTree(state) {
  try {
    if (!isPlainObject(state)) return [];
    const nodes = state.nodes;
    if (!isPlainObject(nodes)) return [];

    const allIds = Object.keys(nodes).filter((id) => isPlainObject(nodes[id]));
    const orderSeed = Array.isArray(state.nodeOrder)
      ? state.nodeOrder.map(String)
      : [];
    const seenInOrder = new Set();
    const order = [];
    for (const id of orderSeed) {
      if (allIds.includes(id) && !seenInOrder.has(id)) {
        order.push(id);
        seenInOrder.add(id);
      }
    }
    for (const id of allIds) {
      if (!seenInOrder.has(id)) {
        order.push(id);
        seenInOrder.add(id);
      }
    }

    const childrenByParent = new Map();
    for (const id of order) {
      const parent = nodes[id].parent;
      if (parent !== null && parent !== undefined && hasNode(nodes, parent)) {
        const key = String(parent);
        if (!childrenByParent.has(key)) childrenByParent.set(key, []);
        childrenByParent.get(key).push(id);
      }
    }
    for (const kids of childrenByParent.values()) {
      kids.sort((a, b) => createdSeqOf(nodes[a]) - createdSeqOf(nodes[b]));
    }

    const visited = new Set();

    function build(id) {
      visited.add(id);
      const kids = childrenByParent.get(id) || [];
      const children = [];
      for (const cid of kids) {
        if (visited.has(cid)) continue;
        children.push(build(cid));
      }
      return { node: nodes[id], children, orphan: false };
    }

    const roots = [];

    for (const id of order) {
      if (visited.has(id)) continue;
      const parent = nodes[id].parent;
      if (parent === null || parent === undefined) {
        roots.push(build(id));
      } else if (!hasNode(nodes, parent)) {
        const entry = build(id);
        entry.orphan = true;
        roots.push(entry);
      }
    }

    for (const id of order) {
      if (visited.has(id)) continue;
      const entry = build(id);
      entry.orphan = true;
      roots.push(entry);
    }

    const pathSet = bestPathSet(state);
    const edges = edgeLabelMap(state);
    for (const root of roots) enrich(root, state, pathSet, edges);
    return roots;
  } catch (_) {
    return [];
  }
}
