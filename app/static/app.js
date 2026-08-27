/** Phase 2: SSE client — reduce + three views. */

import { initial, reduce } from "./reducer.js";

let state = initial();
let runId = null;
let eventsSource = null;
let heartbeatSource = null;
let eventsSince = 0;
let heartbeatSince = 0;

const metaEl = () => document.getElementById("meta");
const treeEl = () => document.getElementById("tree");
const queueEl = () => document.getElementById("queue");
const workersEl = () => document.getElementById("workers");
const logEl = () => document.getElementById("log");

function render() {
  const run = state.run;
  metaEl().textContent = run
    ? `run ${run.id} · ${run.task || "?"} · ${run.protocol_hash || ""} · events@${eventsSince}`
    : `run ${runId || "?"} · events@${eventsSince}`;

  const nodes = Object.values(state.nodes);
  const byParent = new Map();
  for (const n of nodes) {
    const key = n.parent == null ? "root" : String(n.parent);
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(n);
  }
  for (const list of byParent.values()) {
    list.sort((a, b) => a.id - b.id);
  }
  const lines = [];
  function walk(parentKey, depth) {
    const kids = byParent.get(parentKey) || [];
    for (const n of kids) {
      const pad = "  ".repeat(depth);
      lines.push(
        `${pad}#${n.id} ${n.kind} [${n.state}]` +
          (n.parent != null ? ` ← ${n.parent}` : ""),
      );
      walk(String(n.id), depth + 1);
    }
  }
  walk("root", 0);
  treeEl().innerHTML = lines.map((t) => `<li>${escapeHtml(t)}</li>`).join("");

  queueEl().innerHTML = state.queue
    .map((h) => {
      const label = `${h.id} · ${h.stage}/${h.mechanism || "?"}`;
      return `<li>${escapeHtml(label)}</li>`;
    })
    .join("");

  logEl().innerHTML = state.log
    .map((ev) => {
      const bits = [`#${ev.seq}`, ev.type];
      if (ev.node != null) bits.push(`node=${ev.node}`);
      if (ev.class) bits.push(`class=${ev.class}`);
      if (ev.attempt != null) bits.push(`attempt=${ev.attempt}`);
      if (ev.state) bits.push(`state=${ev.state}`);
      bits.push(`— ${ev.summary || ""}`);
      return `<li>${escapeHtml(bits.join(" "))}</li>`;
    })
    .join("");

  workersEl().innerHTML = Object.entries(state.workers)
    .map(([w, ev]) => {
      const label = `${w}: ${ev.status || "?"} node=${ev.node ?? "—"} p=${ev.progress ?? "—"}`;
      return `<li>${escapeHtml(label)}</li>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function connectEvents() {
  if (eventsSource) eventsSource.close();
  eventsSource = new EventSource(`/runs/${runId}/events?since=${eventsSince}`);
  eventsSource.onmessage = (raw) => {
    const ev = JSON.parse(raw.data);
    state = reduce(state, ev);
    eventsSince = ev.seq;
    render();
  };
  eventsSource.onerror = () => {
    eventsSource.close();
    setTimeout(connectEvents, 500);
  };
}

function connectHeartbeat() {
  if (heartbeatSource) heartbeatSource.close();
  heartbeatSource = new EventSource(
    `/runs/${runId}/heartbeat?since=${heartbeatSince}`,
  );
  heartbeatSource.onmessage = (raw) => {
    const ev = JSON.parse(raw.data);
    state = reduce(state, ev);
    heartbeatSince = ev.seq;
    render();
  };
  heartbeatSource.onerror = () => {
    heartbeatSource.close();
    setTimeout(connectHeartbeat, 500);
  };
}

async function resolveRunId() {
  const params = new URLSearchParams(location.search);
  const fromQuery = params.get("run");
  if (fromQuery) return fromQuery;
  const res = await fetch("/runs");
  const runs = await res.json();
  if (!runs.length) throw new Error("no runs found");
  return runs[0].run_id;
}

async function main() {
  try {
    runId = await resolveRunId();
    render();
    connectEvents();
    connectHeartbeat();
  } catch (err) {
    metaEl().textContent = String(err.message || err);
  }
}

main();
