/** App shell: hash router + SSE client. Vanilla JS, no framework, no build step. */

import { initial, reduce } from "./reducer.js";

// --- store: the only thing that knows about reduce(). Routes and the router
// only ever see state via getState()/subscribe() — never an event, never an
// EventSource. ---
function createStore() {
  let state = initial();
  const subscribers = new Set();
  function notify() {
    for (const fn of subscribers) fn(state);
  }
  return {
    getState: () => state,
    applyEvent(ev) {
      state = reduce(state, ev);
      notify();
    },
    replaceState(next) {
      state = next;
      notify();
    },
    subscribe(fn) {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
  };
}

const store = createStore();

let runId = null;
let eventsSource = null;
let heartbeatSource = null;
let eventsSince = 0;
let heartbeatSince = 0;

const metaEl = () => document.getElementById("meta");
const viewEl = () => document.getElementById("view");

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

// --- Dashboard: the existing Phase 2 four-panel view, moved as-is. This is
// the provisional pre-redesign layout (see Handoff_app.md, "Explicitly
// parked" — Dashboard redesign is not this batch); only the container
// changed, from a fixed <main> to a route-owned render function. ---

function buildTreeHtml(state) {
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
  return lines.map((t) => `<li>${escapeHtml(t)}</li>`).join("");
}

function buildQueueHtml(state) {
  return state.queue
    .map((h) => {
      const label = `${h.id} · ${h.stage}/${h.mechanism || "?"}`;
      return `<li>${escapeHtml(label)}</li>`;
    })
    .join("");
}

function buildFeedHtml(state) {
  return state.feed
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
}

function buildWorkersHtml(state) {
  return Object.entries(state.workers)
    .map(([w, ev]) => {
      const prog =
        ev.total != null && ev.total > 0
          ? `${ev.step ?? 0}/${ev.total}`
          : ev.progress != null
            ? String(ev.progress)
            : "—";
      const loss = ev.loss != null ? ` loss=${Number(ev.loss).toFixed(4)}` : "";
      const attempt = ev.attempt != null ? ` attempt=${ev.attempt}` : "";
      const label = `${w}: ${ev.status || "running"} node=${ev.node ?? "—"} step=${prog}${loss}${attempt}`;
      return `<li>${escapeHtml(label)}</li>`;
    })
    .join("");
}

function buildIncumbentHtml(state) {
  const id = state.incumbent;
  if (id == null) return `<li>${escapeHtml("— none yet")}</li>`;
  const node = state.nodes[id];
  const hyp = node?.hypothesisId != null ? String(node.hypothesisId) : "?";
  const st = node?.state != null ? String(node.state) : "?";
  return `<li>${escapeHtml(`#${id} ${hyp} [${st}]`)}</li>`;
}

function renderDashboard(state) {
  viewEl().innerHTML = `
    <div class="dashboard-grid">
      <section>
        <h2>Run tree</h2>
        <ul>${buildTreeHtml(state)}</ul>
      </section>
      <section>
        <h2>Incumbent</h2>
        <ul>${buildIncumbentHtml(state)}</ul>
      </section>
      <section>
        <h2>Hypotheses</h2>
        <ul>${buildQueueHtml(state)}</ul>
      </section>
      <section>
        <h2>Now running</h2>
        <ul>${buildWorkersHtml(state)}</ul>
      </section>
      <section>
        <h2>Event log</h2>
        <ul>${buildFeedHtml(state)}</ul>
      </section>
    </div>
  `;
}

// --- Protocol: read-only, all data from state.run.protocol. Two visually
// distinct tiers — hashed (defines comparability) vs. not-hashed (bounds this
// run only) — per Handoff_app.md. No control here may change a run. ---

function escapeAttr(s) {
  return escapeHtml(s).replaceAll('"', "&quot;");
}

function chip(text, extraClass = "") {
  return `<span class="chip ${extraClass}">${escapeHtml(text)}</span>`;
}

// null/undefined is always an explicit chip, never a blank cell — a blank is
// indistinguishable from a rendering bug against protocols/aliccp.yaml, which
// is mostly null right now.
function renderScalar(value) {
  if (value === null || value === undefined) return chip("not set", "chip-null");
  return escapeHtml(String(value));
}

// Monospaced, click-to-copy (see initClickToCopy) — covers protocol_hash,
// the four sha256 fields, script_sha, and baseline commit. Truncated to 12
// chars only when the value actually looks like a hash (hex, >=32 chars
// after stripping an optional "sha256:" prefix); a readable identifier like
// "synthetic-baseline-v1" is shown in full — truncating it would only make
// it harder to read, since it isn't unreadable in full to begin with. Still
// routes through the same null chip when the value is missing.
function formatHash(value) {
  if (value === null || value === undefined) return chip("not set", "chip-null");
  const str = String(value);
  const remainder = str.replace(/^sha256:/, "");
  const looksLikeHash = /^[0-9a-f]+$/i.test(remainder) && remainder.length >= 32;
  const display = looksLikeHash && str.length > 12 ? `${str.slice(0, 12)}…` : str;
  return `<span class="hash-value" data-copy="${escapeAttr(str)}" title="click to copy full value">${escapeHtml(display)}</span>`;
}

// The spread across seeds *is* the noise band — reproduced renders as
// [min, max] + range, never five loose numbers in a row.
function formatReproduced(arr) {
  if (!Array.isArray(arr) || arr.length === 0) return chip("not set", "chip-null");
  const min = Math.min(...arr);
  const max = Math.max(...arr);
  const fmt = (n) => Number(n.toFixed(6)).toString();
  return `[${fmt(min)}, ${fmt(max)}] <span class="range-note">(range ${fmt(max - min)})</span>`;
}

function kv(label, valueHtml) {
  return `<dt>${escapeHtml(label)}</dt><dd>${valueHtml}</dd>`;
}

function buildDataBlock(data) {
  return `
    <div class="protocol-block">
      <h3>Data</h3>
      <dl class="kv">
        ${kv("ingest_hash", formatHash(data?.ingest_hash))}
        ${kv("train.source", renderScalar(data?.train?.source))}
        ${kv("train.sha256", formatHash(data?.train?.sha256))}
        ${kv("test.source", renderScalar(data?.test?.source))}
        ${kv("test.sha256", formatHash(data?.test?.sha256))}
      </dl>
    </div>
  `;
}

function buildSplitBlock(label, split) {
  return `
    <div class="protocol-block">
      <h3>${escapeHtml(label)}</h3>
      <dl class="kv">
        ${kv("from", renderScalar(split?.from))}
        ${kv("rule", renderScalar(split?.rule))}
        ${kv("sha256", formatHash(split?.sha256))}
      </dl>
    </div>
  `;
}

// cvr_auc's required output (p_conversion_given_click) is the field a
// submission bug hides behind — highlighted by output value, not by metric
// name, so the rule still holds if a protocol ever adds another metric that
// requires it.
function buildMetricsBlock(metrics) {
  const entries = Object.entries(metrics || {});
  if (!entries.length) {
    return `<div class="protocol-block"><h3>Metrics</h3><p>${chip("not set", "chip-null")}</p></div>`;
  }
  const rows = entries
    .map(([name, m]) => {
      const highlight = m && m.output === "p_conversion_given_click";
      return `<tr class="${highlight ? "metric-highlight" : ""}">
        <td>${escapeHtml(name)}</td>
        <td>${renderScalar(m?.population)}</td>
        <td>${renderScalar(m?.positive)}</td>
        <td>${renderScalar(m?.output)}</td>
      </tr>`;
    })
    .join("");
  return `
    <div class="protocol-block">
      <h3>Metrics</h3>
      <table class="metrics">
        <thead><tr><th>Metric</th><th>Population</th><th>Positive</th><th>Required output</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function buildScoringBlock(scoring) {
  return `
    <div class="protocol-block">
      <h3>Scoring</h3>
      <dl class="kv">
        ${kv("script_sha", formatHash(scoring?.script_sha))}
        ${kv("aggregation", renderScalar(scoring?.aggregation))}
      </dl>
    </div>
  `;
}

function buildBaselineBlock(baseline) {
  const published = baseline?.published || {};
  const reproduced = baseline?.reproduced || {};
  const metricNames = [...new Set([...Object.keys(published), ...Object.keys(reproduced)])];
  const rows = metricNames
    .map(
      (name) => `<tr>
        <td>${escapeHtml(name)}</td>
        <td>${renderScalar(published[name])}</td>
        <td>${formatReproduced(reproduced[name])}</td>
      </tr>`,
    )
    .join("");
  return `
    <div class="protocol-block">
      <h3>Baseline</h3>
      <dl class="kv">
        ${kv("repo", renderScalar(baseline?.repo))}
        ${kv("commit", formatHash(baseline?.commit))}
        ${kv("command", renderScalar(baseline?.command))}
      </dl>
      ${
        metricNames.length
          ? `<table class="metrics">
               <thead><tr><th>Metric</th><th>Published</th><th>Reproduced</th></tr></thead>
               <tbody>${rows}</tbody>
             </table>`
          : ""
      }
    </div>
  `;
}

function buildConvergenceBlock(convergence) {
  return `
    <div class="protocol-block">
      <h3>Convergence</h3>
      <dl class="kv">
        ${kv("epsilon", renderScalar(convergence?.epsilon))}
        ${kv("n_rounds", renderScalar(convergence?.n_rounds))}
      </dl>
    </div>
  `;
}

function buildSeedsBlock(seeds) {
  const pinned = Array.isArray(seeds?.pinned) && seeds.pinned.length
    ? escapeHtml(seeds.pinned.join(", "))
    : chip("not set", "chip-null");
  return `
    <div class="protocol-block">
      <h3>Seeds</h3>
      <dl class="kv">
        ${kv("pinned", pinned)}
        ${kv("cuda_deterministic", renderScalar(seeds?.cuda_deterministic))}
      </dl>
    </div>
  `;
}

function buildHashedTier(protocol) {
  const ruler = protocol.ruler || {};
  return `
    <section class="protocol-tier hashed">
      <h2>Hashed — defines comparability</h2>
      <p class="tier-note">Changing any of these fields means results are no longer comparable across runs.</p>
      <div class="protocol-block">
        <dl class="kv">
          ${kv("task", renderScalar(protocol.task))}
          ${kv("schema_version", renderScalar(protocol.schema_version))}
          ${kv("rulebook_version", renderScalar(ruler.rulebook_version))}
          ${kv("protocol_hash", formatHash(protocol.protocol_hash))}
          ${kv("protocol_path", renderScalar(protocol.protocol_path))}
        </dl>
      </div>
      ${buildDataBlock(ruler.data)}
      ${buildSplitBlock("Split — search_validation", ruler.splits?.search_validation)}
      ${buildSplitBlock("Split — holdout_validation", ruler.splits?.holdout_validation)}
      ${buildMetricsBlock(ruler.metrics)}
      ${buildScoringBlock(ruler.scoring)}
      ${buildBaselineBlock(ruler.baseline)}
      ${buildConvergenceBlock(ruler.convergence)}
      ${buildSeedsBlock(ruler.seeds)}
    </section>
  `;
}

function buildNotHashedTier(run) {
  const budget = run?.budget || {};
  return `
    <section class="protocol-tier not-hashed">
      <h2>Not hashed — bounds this run only</h2>
      <p class="tier-note">These values do not affect comparability across runs; they only bound this one.</p>
      <div class="protocol-block">
        <h3>Budget</h3>
        <dl class="kv">
          ${kv("gpu_hours", renderScalar(budget.gpu_hours))}
          ${kv("wall_clock_h", renderScalar(budget.wall_clock_h))}
          ${kv("llm_usd", renderScalar(budget.llm_usd))}
        </dl>
      </div>
      <div class="protocol-block">
        <h3>Workers</h3>
        <p>${renderScalar(run?.workers)}</p>
      </div>
    </section>
  `;
}

function renderProtocol(state) {
  const protocol = state.run.protocol;
  if (!protocol) {
    viewEl().innerHTML = `<p class="waiting">Waiting for run_started…</p>`;
    return;
  }
  viewEl().innerHTML = buildHashedTier(protocol) + buildNotHashedTier(protocol.run);
}

// navigator.clipboard is only defined in a secure context. 127.0.0.1 counts,
// so this works today, but the Report screen is a self-contained offline
// HTML file opened over file://, where it does not — select the text instead
// so the user can still Cmd/Ctrl-C it. Never throws either way.
function selectText(el) {
  try {
    // el's rendered text is the truncated display string, not the full
    // value; selecting it as-is would silently hand the user a partial hash
    // to Cmd/Ctrl-C. Swap in the full value before selecting. Deliberately
    // not auto-reverted on a timer — the user still has to press Cmd/Ctrl-C
    // by hand here, and a timeout could deselect before they do; the next
    // re-render (any state update, or route change) naturally restores the
    // truncated form.
    if (el.dataset.copy && el.dataset.copy !== el.textContent) {
      el.textContent = el.dataset.copy;
    }
    const range = document.createRange();
    range.selectNodeContents(el);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  } catch (_) {
    /* best effort only */
  }
}

function initClickToCopy() {
  viewEl().addEventListener("click", (e) => {
    const target = e.target.closest(".hash-value");
    if (!target || !target.dataset.copy) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(target.dataset.copy).then(
        () => {
          target.classList.add("copied");
          setTimeout(() => target.classList.remove("copied"), 800);
        },
        () => selectText(target), // e.g. denied permission — fall back, don't throw
      );
    } else {
      selectText(target);
    }
  });
}

function renderStub(label) {
  return () => {
    viewEl().innerHTML = `<p class="stub">${escapeHtml(label)} — not built yet.</p>`;
  };
}

// --- router ---
const ROUTES = [
  { hash: "dashboard", render: renderDashboard },
  // key: skip re-rendering Protocol when unrelated state changes (any other
  // event on a live run — measurement ticks, heartbeats) and state.run.protocol
  // itself hasn't. Without this, every route rebuilds #view from scratch on
  // every store update; on Protocol specifically that wipes any in-progress
  // text selection (the click-to-copy fallback, or just a reader selecting
  // text) within milliseconds on an active run. Dashboard has no key because
  // its four panels are meant to reflect every event.
  { hash: "protocol", render: renderProtocol, key: (state) => state.run.protocol },
  { hash: "brief", render: renderStub("Brief") },
  { hash: "research", render: renderStub("Research") },
  { hash: "hypotheses", render: renderStub("Hypotheses") },
  { hash: "run", render: renderStub("Run") },
  { hash: "audit/replication", render: renderStub("Audit — Replication") },
  { hash: "audit/cost", render: renderStub("Audit — Cost") },
  { hash: "audit/reliability", render: renderStub("Audit — Reliability") },
  { hash: "report", render: renderStub("Report") },
];
// Audit has no content of its own — two of its three children are parked
// pending cost and rung data (see Handoff_app.md, "Explicitly parked"), but
// the router needs their shape now so the Protocol page isn't built against
// a router that changes again later.
const REDIRECTS = { audit: "audit/replication" };
const DEFAULT_ROUTE = "dashboard";

function currentRoutePath() {
  return location.hash.replace(/^#\/?/, "").replace(/\/+$/, "");
}

function highlightSidebar(hash) {
  for (const a of document.querySelectorAll("#sidebar a[data-route]")) {
    a.classList.toggle("active", a.dataset.route === hash);
  }
}

let lastRenderedHash = null;
let lastRenderedKey;

function renderRoute() {
  const path = currentRoutePath();
  const redirect = REDIRECTS[path];
  if (redirect) {
    location.hash = `#/${redirect}`; // hashchange re-invokes renderRoute with the resolved path
    return;
  }
  const route = ROUTES.find((r) => r.hash === path) || ROUTES.find((r) => r.hash === DEFAULT_ROUTE);
  highlightSidebar(route.hash);
  const state = store.getState();
  if (route.key) {
    const key = route.key(state);
    if (lastRenderedHash === route.hash && key === lastRenderedKey) return;
    lastRenderedKey = key;
  }
  lastRenderedHash = route.hash;
  route.render(state);
}

function updateMeta(state) {
  const run = state.run;
  metaEl().textContent = run.id
    ? `run ${run.id} · ${run.task || "?"} · ${run.protocolHash || ""} · events@${eventsSince}`
    : `run ${runId || "?"} · events@${eventsSince}`;
}

function renderApp(state) {
  updateMeta(state);
  renderRoute();
}

window.addEventListener("hashchange", renderRoute);
store.subscribe(renderApp);

// --- live source: two EventSource connections, reconnect-with-since and the
// newest-run poller. Unchanged from Phase 2 other than routing through the
// store instead of a bare module-level `state` variable. ---

function connectEvents() {
  if (eventsSource) eventsSource.close();
  eventsSource = new EventSource(`/runs/${runId}/events?since=${eventsSince}`);
  eventsSource.onmessage = (raw) => {
    const ev = JSON.parse(raw.data);
    store.applyEvent(ev);
    eventsSince = ev.seq;
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
    store.applyEvent(ev);
    heartbeatSince = ev.seq;
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

function followNewestRun() {
  const params = new URLSearchParams(location.search);
  if (params.get("run")) return; // pinned by URL: never switch
  setInterval(async () => {
    try {
      const res = await fetch("/runs");
      const runs = await res.json();
      if (runs.length && runs[0].run_id !== runId) {
        runId = runs[0].run_id;
        eventsSince = 0;
        heartbeatSince = 0;
        store.replaceState(initial());
        connectEvents();
        connectHeartbeat();
      }
    } catch (_) {
      /* server away; try again next tick */
    }
  }, 2000);
}

// --- entry point: takes a source, either a live run or a plain array of
// events. Nothing below this function knows which kind it got — the Report
// screen (later; parked this batch) is "the same renderer fed a finished
// run", i.e. startApp(arrayOfEvents), with no other code path touched. ---
function startApp(source) {
  if (Array.isArray(source)) {
    let state = initial();
    for (const ev of source) state = reduce(state, ev);
    store.replaceState(state);
    return;
  }
  runId = source.runId;
  connectEvents();
  connectHeartbeat();
}

async function main() {
  try {
    initClickToCopy();
    if (!location.hash) location.hash = `#/${DEFAULT_ROUTE}`;
    runId = await resolveRunId();
    renderApp(store.getState()); // initial paint: meta + route before first event
    startApp({ runId });
    followNewestRun();
  } catch (err) {
    metaEl().textContent = String(err.message || err);
  }
}

main();
