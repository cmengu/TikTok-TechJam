/** Checkpoint 2 tree reader tests — node --test, no fixtures needed (buildTree takes a plain state object). */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildTree } from "./tree.js";

function makeNode(id, parent, extra = {}) {
  return {
    id,
    parent,
    kind: "draft",
    hypothesisId: `h-${id}`,
    state: "screening",
    stateHistory: [],
    scores: {},
    seeds: [],
    bands: {},
    latestVerdict: null,
    failures: [],
    recoveries: [],
    ruleTrips: [],
    createdSeq: id,
    ...extra,
  };
}

// Walks a buildTree() result and returns every node id it contains, in
// traversal order, plus a duplicate check — used to assert "never drop"
// without caring about exact nesting shape.
function collectIds(roots) {
  const ids = [];
  function walk(entries) {
    for (const entry of entries) {
      ids.push(entry.node.id);
      walk(entry.children);
    }
  }
  walk(roots);
  return ids;
}

describe("tree — normal parentage", () => {
  it("test_roots_are_nodes_with_null_parent", () => {
    const state = {
      nodes: { 1: makeNode(1, null), 2: makeNode(2, 1), 3: makeNode(3, 1) },
      nodeOrder: [1, 2, 3],
    };
    const tree = buildTree(state);
    assert.equal(tree.length, 1);
    assert.equal(tree[0].node.id, 1);
    assert.equal(tree[0].orphan, false);
    assert.equal(tree[0].children.length, 2);
    assert.deepEqual(
      tree[0].children.map((c) => c.node.id),
      [2, 3],
    );
    for (const child of tree[0].children) {
      assert.equal(child.orphan, false);
      assert.deepEqual(child.children, []);
    }
  });

  it("test_children_ordered_by_createdSeq_not_insertion_order", () => {
    const state = {
      // Inserted in reverse createdSeq order to prove sorting, not object
      // insertion order, decides the child ordering.
      nodes: {
        1: makeNode(1, null, { createdSeq: 0 }),
        3: makeNode(3, 1, { createdSeq: 20 }),
        2: makeNode(2, 1, { createdSeq: 10 }),
      },
      nodeOrder: [1, 3, 2],
    };
    const tree = buildTree(state);
    assert.equal(tree.length, 1);
    assert.deepEqual(
      tree[0].children.map((c) => c.node.id),
      [2, 3],
    );
  });

  it("test_multiple_roots_and_deep_nesting", () => {
    const state = {
      nodes: {
        1: makeNode(1, null, { createdSeq: 0 }),
        2: makeNode(2, null, { createdSeq: 1 }),
        3: makeNode(3, 1, { createdSeq: 2 }),
        4: makeNode(4, 3, { createdSeq: 3 }),
      },
      nodeOrder: [1, 2, 3, 4],
    };
    const tree = buildTree(state);
    assert.equal(tree.length, 2);
    assert.deepEqual(
      tree.map((r) => r.node.id),
      [1, 2],
    );
    const nodeOneEntry = tree.find((r) => r.node.id === 1);
    assert.equal(nodeOneEntry.children[0].node.id, 3);
    assert.equal(nodeOneEntry.children[0].children[0].node.id, 4);
  });
});

describe("tree — orphan", () => {
  it("test_missing_parent_id_is_returned_at_root_as_orphan", () => {
    const state = {
      nodes: { 5: makeNode(5, 99) }, // 99 is never a node
      nodeOrder: [5],
    };
    const tree = buildTree(state);
    assert.equal(tree.length, 1);
    assert.equal(tree[0].node.id, 5);
    assert.equal(tree[0].orphan, true);
    assert.deepEqual(tree[0].children, []);
  });

  it("test_orphan_is_never_dropped_alongside_normal_nodes", () => {
    const state = {
      nodes: {
        1: makeNode(1, null),
        2: makeNode(2, 1),
        9: makeNode(9, 404), // orphan, unrelated parent id
      },
      nodeOrder: [1, 2, 9],
    };
    const tree = buildTree(state);
    const ids = collectIds(tree).sort();
    assert.deepEqual(ids, [1, 2, 9]);
    const orphanRoot = tree.find((r) => r.node.id === 9);
    assert.ok(orphanRoot, "orphan node must appear at root level");
    assert.equal(orphanRoot.orphan, true);
  });
});

describe("tree — cycle", () => {
  it("test_mutual_parent_cycle_does_not_infinite_loop_and_keeps_both_nodes", () => {
    const state = {
      nodes: {
        1: makeNode(1, 2, { createdSeq: 0 }),
        2: makeNode(2, 1, { createdSeq: 1 }),
      },
      nodeOrder: [1, 2],
    };
    const tree = buildTree(state); // must return, not hang
    const ids = collectIds(tree).sort();
    assert.deepEqual(ids, [1, 2]);
    // exactly one entry (somewhere in the tree) is marked orphan — the cut
    // point that broke the cycle — and it sits at root level.
    assert.equal(tree.length, 1);
    assert.equal(tree[0].orphan, true);
  });

  it("test_self_parent_cycle_does_not_infinite_loop", () => {
    const state = {
      nodes: { 7: makeNode(7, 7) },
      nodeOrder: [7],
    };
    const tree = buildTree(state);
    assert.equal(tree.length, 1);
    assert.equal(tree[0].node.id, 7);
    assert.equal(tree[0].orphan, true);
    assert.deepEqual(tree[0].children, []);
  });

  it("test_three_node_cycle_keeps_all_three_nodes", () => {
    const state = {
      nodes: {
        1: makeNode(1, 2, { createdSeq: 0 }),
        2: makeNode(2, 3, { createdSeq: 1 }),
        3: makeNode(3, 1, { createdSeq: 2 }),
      },
      nodeOrder: [1, 2, 3],
    };
    const tree = buildTree(state);
    const ids = collectIds(tree).sort();
    assert.deepEqual(ids, [1, 2, 3]);
  });

  it("test_cycle_with_a_normal_child_hanging_off_it_keeps_the_child", () => {
    // A <-> B cycle, plus C, a normal (non-cycle) node parented on A.
    const state = {
      nodes: {
        1: makeNode(1, 2, { createdSeq: 0 }), // A
        2: makeNode(2, 1, { createdSeq: 1 }), // B
        3: makeNode(3, 1, { createdSeq: 2 }), // C, child of A
      },
      nodeOrder: [1, 2, 3],
    };
    const tree = buildTree(state);
    const ids = collectIds(tree).sort();
    assert.deepEqual(ids, [1, 2, 3]);
  });
});

describe("tree — empty state", () => {
  it("test_empty_nodes_returns_empty_array", () => {
    assert.deepEqual(buildTree({ nodes: {}, nodeOrder: [] }), []);
  });

  it("test_no_nodes_key_returns_empty_array", () => {
    assert.deepEqual(buildTree({}), []);
  });
});

describe("tree — total: never throws", () => {
  it("test_never_throws_on_malformed_input", () => {
    const inputs = [
      null,
      undefined,
      42,
      "state",
      [],
      { nodes: null },
      { nodes: undefined },
      { nodes: "garbage" },
      { nodes: [] },
      { nodes: { 1: null }, nodeOrder: [1] },
      { nodes: { 1: "not an object" }, nodeOrder: [1] },
      { nodes: { 1: makeNode(1, null) }, nodeOrder: "not an array" },
      { nodes: { 1: makeNode(1, null) } }, // no nodeOrder at all
    ];
    for (const input of inputs) {
      assert.doesNotThrow(() => buildTree(input), `threw on ${JSON.stringify(input)}`);
    }
  });

  it("test_never_throws_and_returns_array_even_when_id_types_mismatch", () => {
    // node ids come from the wire as numbers (node_created.id); parent
    // references should resolve regardless of number/string mismatches.
    const state = {
      nodes: { 1: makeNode(1, null), 2: makeNode(2, "1") },
      nodeOrder: [1, 2],
    };
    assert.doesNotThrow(() => buildTree(state));
    const tree = buildTree(state);
    const ids = collectIds(tree).sort();
    assert.deepEqual(ids, [1, 2]);
  });
});
