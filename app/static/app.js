/** App shell: hash router + SSE client. Vanilla JS, no framework, no build step. */

import { initial, reduce } from "./reducer.js";
import { verdictAnnotation } from "./band.js";

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

// --- Dashboard: five panels answering "is it alive, what's it doing, how far
// along, is anything wrong" per the product spec (Handoff_app.md, Task 5).
// This batch builds panels 1-3 only; 4 (stopping progress) and 5 (paper
// ticker) land next checkpoint. No control here may change a run. ---

// Heartbeat cadence isn't specified anywhere; 5s is a judgment call for "the
// worker has gone quiet" that comfortably exceeds normal inter-heartbeat gaps
// even at the fake-run's default 20x speed.
const WORKER_STALE_MS = 5000;

function buildNowRunningPanel(state, nowMs) {
  const entries = Object.entries(state.workers);
  if (!entries.length) return `<p class="panel-empty">no workers yet</p>`;
  const rows = entries
    .map(([worker, ev]) => {
      const heartbeatMs = ev.t ? new Date(ev.t).getTime() : NaN;
      // reducer.js:397 sets run.status to "ended" on run_ended; once the run
      // has ended, heartbeat silence is expected, not a fault, so the stale
      // test is meaningless there.
      const stale =
        state.run.status !== "ended" &&
        Number.isFinite(heartbeatMs) &&
        nowMs - heartbeatMs > WORKER_STALE_MS;
      const prog =
        ev.total != null && ev.total > 0
          ? `${ev.step ?? 0}/${ev.total}`
          : ev.progress != null
            ? String(ev.progress)
            : "—";
      const bits = [`node ${ev.node ?? "—"}`, `step ${prog}`];
      if (ev.loss != null) bits.push(`loss ${Number(ev.loss).toFixed(4)}`);
      if (ev.attempt != null) bits.push(`attempt ${ev.attempt}`);
      const label = `${worker}: ${ev.status || "running"} — ${bits.join(" · ")}`;
      const staleTag = stale ? ` ${chip("stale", "chip-null")}` : "";
      return `<li class="${stale ? "worker-stale" : ""}">${escapeHtml(label)}${staleTag}</li>`;
    })
    .join("");
  return `<ul class="worker-list">${rows}</ul>`;
}

function mean(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

// The incumbent for a metric is the latest verdict that actually promoted a
// node on it — not just the latest verdict, which might be a screen tick on
// an unrelated node.
function latestPromoted(state, metric) {
  for (let i = state.verdicts.length - 1; i >= 0; i--) {
    const v = state.verdicts[i];
    if (v.metric === metric && v.state === "promoted") return v;
  }
  return null;
}

// The app reports the harness's verdict; it never computes or overrides one.
// The number is always shown — every row reaching this panel is a replicate
// pass (see latestPromoted, which filters to state === "promoted"), so by
// definition it cleared the bar. Nothing here greys a promoted verdict.
// The value shown is a SCORE (mean of verdict.scores), not delta_mean:
// this column answers "where does the incumbent stand against the published
// baseline", not "did this node beat the previous incumbent" — that's the
// node dossier's question (Handoff_app.md, "Task 6"). verdictAnnotation's
// text/reason still comes from the delta the harness actually compared.
function renderScoreCell(verdict) {
  if (!verdict || !Array.isArray(verdict.scores) || !verdict.scores.length) {
    return chip("not yet promoted", "chip-null");
  }
  const value = mean(verdict.scores);
  const { text, reason } = verdictAnnotation(verdict);
  const note = text
    ? `<span class="band-note">(${escapeHtml(text)})</span>`
    : `<span class="band-note" title="${escapeHtml(reason)}">(${escapeHtml(reason)})</span>`;
  return `<span class="score-value">${fmtNum(value)}</span> ${note}`;
}

function buildScorePanel(state) {
  const protocol = state.run.protocol;
  if (!protocol) return `<p class="waiting">Waiting for run_started…</p>`;
  const ruler = protocol.ruler || {};
  const metricNames = Object.keys(ruler.metrics || {});
  if (!metricNames.length) return `<p class="panel-empty">no metrics defined</p>`;
  const published = ruler.baseline?.published || {};
  const reproduced = ruler.baseline?.reproduced || {};
  const rows = metricNames
    .map(
      (metric) => `<tr>
        <td>${escapeHtml(metric)}</td>
        <td>${renderScalar(published[metric])}</td>
        <td>${formatReproduced(reproduced[metric])}</td>
        <td>${renderScoreCell(latestPromoted(state, metric))}</td>
      </tr>`,
    )
    .join("");
  return `
    <table class="metrics score-table">
      <thead><tr><th>Metric</th><th>Published</th><th>Reproduced</th><th>Incumbent</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="hdr-dim panel-note" title="a promoted verdict's band tests whether the replicate agreed with the screen, not whether the lead over baseline clears run-to-run noise. harness/measure.py::calibrate is implemented and computes a Band from screen/full run noise, but nothing in the harness compares that Band — or the incumbent's score — against protocol.ruler.baseline.published for significance">vs-baseline significance: not yet instrumented</p>
  `;
}

// A verdict's event "kind" for feed purposes is its outcome state, not the
// generic "verdict" type — inconclusive and rejected must never collapse
// into each other or into a shared "verdict" bucket.
function feedKind(ev) {
  return ev.type === "verdict" ? ev.state || "verdict" : ev.type;
}

function feedLabel(kind) {
  return kind.replaceAll("_", " ");
}

function collapseFeed(feed) {
  const groups = [];
  for (const ev of feed) {
    const kind = feedKind(ev);
    const last = groups[groups.length - 1];
    if (last && last.kind === kind) {
      last.count += 1;
      last.last = ev;
    } else {
      groups.push({ kind, count: 1, first: ev, last: ev });
    }
  }
  return groups;
}

function buildEventsPanel(state) {
  const groups = collapseFeed(state.feed);
  const lastFive = groups.slice(-5).reverse();
  if (!lastFive.length) return `<p class="panel-empty">no events yet</p>`;
  const rows = lastFive
    .map((g) => {
      const label = feedLabel(g.kind);
      if (g.count === 1) {
        const ev = g.last;
        const bits = [`#${ev.seq}`, label];
        if (ev.node != null) bits.push(`node=${ev.node}`);
        if (ev.class) bits.push(`class=${ev.class}`);
        if (ev.attempt != null) bits.push(`attempt=${ev.attempt}`);
        bits.push(`— ${ev.summary || ""}`);
        return `<li>${escapeHtml(bits.join(" "))}</li>`;
      }
      const text = `#${g.first.seq}–#${g.last.seq} ${g.count}× ${label} — ${g.last.summary || ""}`;
      return `<li>${escapeHtml(text)}</li>`;
    })
    .join("");
  return `<ul class="event-list">${rows}</ul>`;
}

// Counts verdicts after the most recent "promoted" one (all of them, if
// there has been no promotion yet). This is NOT the harness's convergence
// counter — harness/outputs.py::Convergence.update(searchval_score) tracks
// whether the search-validation score has stopped improving by more than
// epsilon across n_rounds, a different quantity, and it raises
// NotImplementedError today regardless. It also can't be reconstructed from
// the event stream: measurement events carry {node, metric, value, seed}
// with no split label, so search-validation and holdout scores are
// indistinguishable here. This count is a stand-in derived in the view from
// state.verdicts, never presented as harness-reported.
function verdictsSinceLastPromoted(state) {
  const verdicts = state.verdicts;
  for (let i = verdicts.length - 1; i >= 0; i--) {
    if (verdicts[i].state === "promoted") return verdicts.length - 1 - i;
  }
  return verdicts.length;
}

function buildStoppingPanel(state) {
  const protocol = state.run.protocol;
  if (!protocol) return `<p class="waiting">Waiting for run_started…</p>`;
  const convergence = protocol.ruler?.convergence || {};
  const since = verdictsSinceLastPromoted(state);
  return `
    <p class="derived-note" title="harness/outputs.py::Convergence.update(searchval_score) is specified to track rounds without improvement and does not yet (raises NotImplementedError) — nothing below is that counter">${chip("derived in the app", "chip-derived")}</p>
    <dl class="kv">
      ${kv("epsilon (protocol target)", renderScalar(convergence.epsilon))}
      ${kv("n_rounds (protocol target)", renderScalar(convergence.n_rounds))}
    </dl>
    <p class="panel-note" title="counts verdicts in state.verdicts since the last one with state === &quot;promoted&quot; — not the harness's rounds-without-improvement count, which does not exist yet">verdicts since last promotion: ${since} (not the convergence counter — the harness's rounds-without-improvement count does not exist yet)</p>
  `;
}

// Titles only — the Research tab (out of scope this batch) is where a paper
// is attached to the hypothesis it produced.
function buildPaperTickerPanel(state) {
  const research = state.research;
  const titles = research.sources.map((s) => s.title).filter(Boolean);
  const list = titles.length
    ? `<ul class="ticker">${titles.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
    : `<p class="panel-empty">no research sources yet</p>`;
  return `
    ${list}
    <p class="cache-tally">cache hits: ${research.hits} · misses: ${research.misses}</p>
  `;
}

function renderDashboard(state) {
  const nowMs = Date.now();
  viewEl().innerHTML = `
    <div class="dashboard-grid">
      <section>
        <h2>Now running</h2>
        ${buildNowRunningPanel(state, nowMs)}
      </section>
      <section>
        <h2>Score against baseline</h2>
        ${buildScorePanel(state)}
      </section>
      <section>
        <h2>Last five events</h2>
        ${buildEventsPanel(state)}
      </section>
      <section>
        <h2>Progress toward stopping</h2>
        ${buildStoppingPanel(state)}
      </section>
      <section>
        <h2>Paper ticker</h2>
        ${buildPaperTickerPanel(state)}
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

// --- header strip: visible on every route. Reads only from reduced state,
// plus wall-clock time for the elapsed figure — the reducer stays pure (no
// Date.now()), so the view owns the one clock that needs it. Handoff_app.md,
// "header strip". ---

function fmtNum(n) {
  return Number(n.toFixed(6)).toString();
}

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function dot(colorClass) {
  return `<span class="hdr-dot ${colorClass}"></span>`;
}

function renderRunStateSlot(run) {
  let colorClass = "dot-grey";
  let text = "waiting";
  if (run.status === "running") {
    colorClass = "dot-green";
    text = "running";
  } else if (run.status === "ended") {
    colorClass = "dot-grey";
    text = run.endReason ? `ended — ${run.endReason}` : "ended";
  }
  document.getElementById("hdr-run-state").innerHTML =
    `${dot(colorClass)}${escapeHtml(text)}`;
}

// submission_written carries only {node, path, summary} — no validity field.
// Validation is the teammate's phase 9/10 and does not exist in the stream
// yet, so this reports what happened (a file was written), not a verdict on
// it. Same honesty rule as spend: say what the stream says, nothing more.
function renderSubmissionSlot(state) {
  const written = state.submissions.length > 0;
  const colorClass = written ? "dot-green" : "dot-amber";
  const text = written ? "submission written" : "no submission yet";
  const title = written
    ? ' title="written from a promoted node; not validated — rulebook post-checks are not instrumented yet"'
    : "";
  document.getElementById("hdr-submission-light").innerHTML =
    `<span${title}>${dot(colorClass)}${escapeHtml(text)}</span>`;
}

// Spend is parked (see Handoff_app.md): no cost data exists in the event
// stream. A dimmed em dash is a visible gap; a computed zero would look like
// a real reading and be worse than the gap it hides.
function renderSpendSlot() {
  document.getElementById("hdr-spend").innerHTML =
    `<span class="hdr-dim" title="spend is not yet instrumented — no cost data in the event stream">spend —</span>`;
}

function renderInterventionsSlot(state) {
  document.getElementById("hdr-interventions").textContent =
    `interventions: ${state.interventions.length}`;
}

function renderElapsedBudgetSlot(run) {
  const el = document.getElementById("hdr-elapsed-budget");
  if (!run.startedAt) {
    el.textContent = "not started";
    return;
  }
  const end = run.status === "ended" && run.endedAt ? new Date(run.endedAt) : new Date();
  const elapsed = formatDuration(end - new Date(run.startedAt));
  const budgetH = run.protocol?.run?.budget?.wall_clock_h;
  if (budgetH == null) {
    el.innerHTML = `${escapeHtml(elapsed)} ${chip("no budget set", "chip-null")}`;
  } else {
    el.textContent = `${elapsed} / ${fmtNum(budgetH)}h budget`;
  }
}

function renderHeader(state) {
  renderRunStateSlot(state.run);
  renderSubmissionSlot(state);
  renderSpendSlot();
  renderInterventionsSlot(state);
  renderElapsedBudgetSlot(state.run);
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
  // reducer.js:149 sets lastSeq synchronously inside reduce(), before
  // store.applyEvent()'s notify() fires — the module-level eventsSince
  // variable below is only reassigned *after* notify() returns (line 783),
  // so a render triggered by that same applyEvent() would see the previous
  // value. state.lastSeq is always current at render time.
  metaEl().textContent = run.id
    ? `run ${run.id} · ${run.task || "?"} · ${run.protocolHash || ""} · events@${state.lastSeq}`
    : `run ${runId || "?"} · events@${state.lastSeq}`;
}

function renderApp(state) {
  renderHeader(state);
  if (state.run.status === "ended") stopHeaderTick();
  else startHeaderTick();
  updateMeta(state);
  renderRoute();
}

window.addEventListener("hashchange", renderRoute);
store.subscribe(renderApp);

// Elapsed-vs-budget needs to tick even when no new event arrives. This is the
// only interval in the app and it touches the header alone — never
// renderRoute() — so an in-progress route (e.g. a text selection on
// Protocol) is never disturbed by the clock. Stopped once the run ends: the
// elapsed value is frozen at endedAt by then, so a still-firing tick would
// only repaint the same text forever. Restarted by renderApp if
// followNewestRun later swings onto a fresh (non-ended) run.
let headerTickId = null;

function startHeaderTick() {
  if (headerTickId != null) return;
  headerTickId = setInterval(() => renderHeader(store.getState()), 1000);
}

function stopHeaderTick() {
  if (headerTickId == null) return;
  clearInterval(headerTickId);
  headerTickId = null;
}

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
