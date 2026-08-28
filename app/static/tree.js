/** Checkpoint 2: pure flat-node-map -> nested tree reader (no DOM, no app.js imports). Contract: context/Handoff_app.md, "Task 7". */

function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function createdSeqOf(node) {
  return node && Number.isFinite(node.createdSeq) ? node.createdSeq : 0;
}

// state.nodes is keyed by node id; ids may be numbers (as emitted by
// node_created) or strings — plain-object property access coerces either
// way, so lookups below never need to normalise the id's original type.
function hasNode(nodes, id) {
  return (
    id !== null &&
    id !== undefined &&
    Object.prototype.hasOwnProperty.call(nodes, id) &&
    isPlainObject(nodes[id])
  );
}

// buildTree(state) -> array of root nodes, each { node, children, orphan }.
// children is the same shape recursively, ordered by createdSeq. Never
// throws and never drops a node from state.nodes, no matter how malformed
// the input — every rule below exists because of a past bug (see
// Handoff_app.md, "Task 7").
export function buildTree(state) {
  try {
    if (!isPlainObject(state)) return [];
    const nodes = state.nodes;
    if (!isPlainObject(nodes)) return [];

    // Stable id order: state.nodeOrder (creation order) first, falling back
    // to whatever Object.keys gives us for any id it missed — nodeOrder is
    // trusted but not required, since this module must stay total even
    // against a hand-built or malformed state.
    const allIds = Object.keys(nodes).filter((id) => isPlainObject(nodes[id]));
    const orderSeed = Array.isArray(state.nodeOrder) ? state.nodeOrder.map(String) : [];
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

    // parentId -> [childId, ...], sorted by createdSeq once, up front — each
    // node contributes to exactly one parent's list (its own `parent`
    // field), so this map is a proper forest-plus-cycles description of the
    // graph before any traversal happens.
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
        // A node can only appear in one parent's kid list (its own `parent`
        // field decides which), so "already visited" here means we walked
        // back into an ancestor via a parent cycle. Cut the edge instead of
        // recursing again — the node itself is not lost, it is already
        // present higher up in this same tree.
        if (visited.has(cid)) continue;
        children.push(build(cid));
      }
      return { node: nodes[id], children, orphan: false };
    }

    const roots = [];

    // Pass 1: real roots (parent === null) and orphans (parent id not
    // present in state.nodes). Orphans are never dropped — silently
    // dropping data was the queue_reordered bug in batch 1.
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

    // Pass 2: whatever is still unvisited belongs to a parent cycle with no
    // null/missing parent anywhere in it (every member's parent resolves to
    // another present node, all the way around). Surface it at root level
    // instead of infinite-looping or dropping it.
    for (const id of order) {
      if (visited.has(id)) continue;
      const entry = build(id);
      entry.orphan = true;
      roots.push(entry);
    }

    return roots;
  } catch (_) {
    return [];
  }
}
