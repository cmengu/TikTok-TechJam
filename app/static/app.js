/** App shell: hash router + SSE client. Vanilla JS, no framework, no build step. */

import { initial, reduce } from "./reducer.js";
import { verdictAnnotation } from "./band.js";
import { buildTree } from "./tree.js";
import { buildDossier, buildAttemptTrail } from "./dossier.js";
import { buildClaimCard, claimCardHtml } from "./claimcard.js";
import { buildMonitors } from "./monitors.js";
import { buildWall, wallHtml } from "./wall.js";
import { buildRung, buildLastMove, buildCascadeCounter, buildHero, heroHtml, provenanceCounts } from "./dashboard.js";
import { stampHtml, provenanceTileHtml } from "./provenance.js";
import { DICT, stateLabel, rungLabel, attributionLabel, moveLabel, fmtScore, fmtDelta, fmtPublished, eventTypeLabel } from "./copy.js";
import { sentence, buildMoveTrail } from "./feed.js";
import { backoffDelay, liveness, runPickerLabel, stalledText } from "./liveness.js";
import { chipHtml, escapeHtml, escapeAttr } from "./chip.js";
import { buildJourney, journeyStripHtml, buildReceipt } from "./journey.js";
import {
  TOUR_STOPS,
  shouldShowTour,
  markTourDone,
  tourOverlayHtml,
  tourStopRoute,
  paneScrollTarget,
} from "./tour.js";
import { buildTrace } from "./trace.js";
import { buildBrief, briefPageHtml } from "./brief.js";
import { buildRulebook, rulebookPageHtml } from "./rulebook.js";
import { buildMemory, memoryPageHtml } from "./memory.js";
import { buildLibrary, libraryPageHtml } from "./library.js";
import { buildIdeas, ideasPageHtml } from "./ideas.js";
import {
  buildDoubleChecks,
  buildSpend,
  buildStability,
  doubleChecksPageHtml,
  spendPageHtml,
  stabilityPageHtml,
} from "./audit.js";
import { buildReport, buildReportHero, reportPageHtml } from "./report.js";

export { chipHtml };

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

// --- Stale-server banner (fix list item 11). Endpoints ship with the page,
// so a 404 from an endpoint this page knows about means the serving process
// predates the page — the honest thing to say is "restart it", once and
// dismissibly, instead of leaving silent empty panels. Every page-content
// fetch chain routes its Response through flagStaleServer before .json(). ---
let staleServerDismissed = false;

function flagStaleServer(res) {
  if (res && res.status === 404 && !staleServerDismissed) {
    const el = document.getElementById("stale-server-banner");
    if (el) el.hidden = false;
  }
  return res;
}

function initStaleServerBanner() {
  const text = document.getElementById("stale-server-text");
  if (text) text.textContent = DICT.staleServer.word;
  const btn = document.getElementById("stale-server-dismiss");
  if (btn) {
    btn.textContent = DICT.staleServerDismiss.word;
    btn.addEventListener("click", () => {
      staleServerDismissed = true;
      const el = document.getElementById("stale-server-banner");
      if (el) el.hidden = true;
    });
  }
}

function requireView() {
  const el = document.getElementById("view");
  if (!el) {
    throw new Error(
      'Missing #view — hard-refresh (Cmd+Shift+R). Old cached index.html has no #view.',
    );
  }
  return el;
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
      <thead><tr><th>Metric</th><th>Published</th><th>Reproduced</th><th>${escapeHtml(DICT.incumbent.word)}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="hdr-dim panel-note" title="${escapeAttr(DICT.baselineSignificanceNote.word)}">vs-baseline significance: not yet instrumented</p>
  `;
}

// A verdict's event "kind" for feed purposes is its outcome state, not the
// generic "verdict" type — inconclusive and rejected must never collapse
// into each other or into a shared "verdict" bucket.
function feedKind(ev) {
  return ev.type === "verdict" ? ev.state || "verdict" : ev.type;
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

function chipStateModifier(state) {
  const map = {
    promoted: "accepted",
    rejected: "declined",
    inconclusive: "retrying",
    retired: "shelved",
    leaked: "disqualified",
    failed: "crashed",
    screening: "live",
    running: "live",
    replicating: "live",
    debugging: "live",
  };
  return map[state] || null;
}

function buildEventRow(g) {
  const ev = g.last;
  const text =
    g.count === 1 ? sentence(ev) : `${g.count}× ${sentence(ev)}`;
  const mod = ev.type === "verdict" ? chipStateModifier(ev.state) : null;
  const stateChip =
    mod != null ? `${chipHtml(stateLabel(ev.state), mod)} ` : "";
  const body =
    ev.node != null
      ? `<a href="#/run/${escapeAttr(String(ev.node))}">${escapeHtml(text)}</a>`
      : escapeHtml(text);
  return `<li>${stateChip}${body}</li>`;
}

// A gap is a run of seq numbers skipped between two known boundary seqs
// (never negative — highSeq and lowSeq are always adjacent group boundaries,
// or a group boundary against the run's seq=1 start or state.lastSeq).
// feedGaps records what was skipped (reducer.js), so we can usually name the
// types; when feedGaps has nothing for this range (e.g. capped out), fall
// back to a bare count.
function buildGapRow(highSeq, lowSeq, feedGaps) {
  const count = highSeq - lowSeq - 1;
  if (count <= 0) return "";
  const skipped = feedGaps.filter((g) => g.seq > lowSeq && g.seq < highSeq);
  if (!skipped.length) {
    return `<li class="feed-gap">#${highSeq}–#${lowSeq} — ${count} event${count === 1 ? "" : "s"} not shown</li>`;
  }
  const byType = new Map();
  for (const g of skipped) {
    byType.set(g.type, (byType.get(g.type) || 0) + 1);
  }
  // Viewers read plain words; the raw event types stay on the hover
  // (flagged on PR #60 — the marker rendered "2 research_source").
  const summary = [...byType.entries()]
    .map(([type, n]) => `${n} ${eventTypeLabel(type, n)}`)
    .join(", ");
  const rawTypes = [...byType.entries()]
    .map(([type, n]) => `${n}\u00d7 ${type}`)
    .join(", ");
  return `<li class="feed-gap" title="${escapeAttr(rawTypes)}">#${highSeq}–#${lowSeq} — ${summary}</li>`;
}

function buildEventsPanel(state) {
  const groups = collapseFeed(state.feed);
  const all = groups.slice().reverse();
  const feedGaps = state.feedGaps;
  if (!all.length) return `<p class="panel-empty">no events yet</p>`;
  const rows = [];
  rows.push(buildGapRow(state.lastSeq, all[0].last.seq, feedGaps));
  all.forEach((g, i) => {
    rows.push(buildEventRow(g));
    if (i < all.length - 1) {
      rows.push(buildGapRow(g.first.seq, all[i + 1].last.seq, feedGaps));
    }
  });
  rows.push(buildGapRow(all[all.length - 1].first.seq, 1, feedGaps));
  return `<div class="event-scroll"><ul class="event-list">${rows.join("")}</ul></div>`;
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
    <p class="panel-note" title="${escapeAttr(DICT.sinceWinTitle.word)}">decisions since last accepted win: ${since} (not the convergence counter — the run does not yet track rounds without improvement)</p>
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

let dashboardRung = { level: "—", reason: "—" };
let dashboardMonitors = { available: false };
let cachedContract = null;
function ensureContract() {
  if (cachedContract != null || ensureContract.inFlight) return;
  ensureContract.inFlight = true;
  fetch("/contract")
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      cachedContract = payload;
      renderRoute();
    })
    .catch(() => {
      cachedContract = { available: false };
    })
    .finally(() => {
      ensureContract.inFlight = false;
    });
}
let dashboardRungFetchGen = 0;
let dashboardRungInFlight = false;

function ensureDashboardRungFetch() {
  if (!runId || dashboardRungInFlight) return;
  const path = currentRoutePath();
  const gen = ++dashboardRungFetchGen;
  dashboardRungInFlight = true;
  fetch(`/runs/${runId}/audit/monitors`)
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== dashboardRungFetchGen) return;
      if (currentRoutePath() !== path) return;
      dashboardMonitors = payload;
      dashboardRung = buildRung(payload);
      const view = requireView();
      const rungEl = view.querySelector("[data-dashboard-rung]");
      if (rungEl) {
        rungEl.innerHTML = `<h2>${escapeHtml(DICT.rungHeading.word)}</h2>${renderRungStrip(dashboardRung)}`;
      }
      const heroEl = view.querySelector("[data-dashboard-hero]");
      if (heroEl) {
        const st = store.getState();
        heroEl.innerHTML = heroHtml(
          buildHero(dashboardMonitors, buildTrace(st), heroLiveContext(st)),
        );
      }
    })
    .catch(() => {
      if (gen !== dashboardRungFetchGen) return;
      if (currentRoutePath() !== path) return;
      dashboardMonitors = { available: false };
      dashboardRung = buildRung({ available: false });
      const view = requireView();
      const rungEl = view.querySelector("[data-dashboard-rung]");
      if (rungEl) {
        rungEl.innerHTML = `<h2>${escapeHtml(DICT.rungHeading.word)}</h2>${renderRungStrip(dashboardRung)}`;
      }
    })
    .finally(() => {
      if (gen === dashboardRungFetchGen) dashboardRungInFlight = false;
    });
}

function renderRungStrip(rung) {
  return `<p>${escapeHtml(rung.level)}</p><p class="panel-note">${escapeHtml(rung.reason)}</p>`;
}


const LIVE_NODE_STATES = new Set([
  "screening",
  "running",
  "replicating",
  "debugging",
]);

// The empty hero's one sentence is state-aware ("attempt N is running" vs
// "waiting" vs "run ended") — this is the state it needs, shared by both
// hero render sites.
function heroLiveContext(state) {
  const live = (state.nodeOrder || [])
    .map((id) => state.nodes[id])
    .find((n) => n && LIVE_NODE_STATES.has(n.state));
  return { attempt: live ? live.id : null, runStatus: state.run.status };
}

function liveStatusHtml(state, nowMs) {
  const live = (state.nodeOrder || [])
    .map((id) => state.nodes[id])
    .find((n) => n && LIVE_NODE_STATES.has(n.state));
  if (!live) {
    const text = state.run.status === "ended" ? "run ended" : "no attempt live";
    return `<p class="dashboard-live">${escapeHtml(text)}</p>`;
  }
  const journey = buildJourney(state, live.id);
  const current = journey?.stages?.find((s) => s.status === "current");
  const stage = current?.label ?? stateLabel(live.state).word;
  let elapsed = "—";
  if (state.run.startedAt) {
    const end = state.run.endedAt ? new Date(state.run.endedAt) : nowMs;
    elapsed = formatDuration(end - new Date(state.run.startedAt));
  }
  return `<p class="dashboard-live">attempt #${escapeHtml(String(live.id))} · ${escapeHtml(stage)} · ${escapeHtml(elapsed)}</p>`;
}

function renderDashboard(state) {
  const nowMs = Date.now();
  // buildEventsPanel's list is newest-first and can run to hundreds of rows
  // (FEED_CAP=1000); renderDashboard replaces #view's innerHTML on every
  // event, which would otherwise reset .event-scroll to the top on each
  // tick. Preserve it — but only when the reader has actually scrolled down
  // (scrollTop > 0): at 0 they're watching the live edge, and pinning them
  // there keeps new events visible instead of freezing the view.
  const prevScrollEl = requireView().querySelector(".event-scroll");
  const prevScrollTop = prevScrollEl ? prevScrollEl.scrollTop : 0;
  const lastMove = buildLastMove(state);
  const cascade = buildCascadeCounter(state);
  const lastMoveBody = lastMove
    ? `<p>round ${escapeHtml(String(lastMove.round))} · ${escapeHtml(String(lastMove.kind))} · parent ${escapeHtml(String(lastMove.parent))}</p>
       <p class="panel-note">${escapeHtml(String(lastMove.reason))}</p>`
    : `<p class="panel-empty">no moves yet</p>`;
  requireView().innerHTML = `
    <section class="card dashboard-hero" data-dashboard-hero>
      ${heroHtml(buildHero(dashboardMonitors, buildTrace(state), heroLiveContext(state)))}
      ${provenanceTileHtml(provenanceCounts(state))}
    </section>
    ${liveStatusHtml(state, nowMs)}
    <div class="dashboard-strip">
      <section data-dashboard-rung>
        <h2>${escapeHtml(DICT.rungHeading.word)}</h2>
        ${renderRungStrip(dashboardRung)}
      </section>
      <section>
        <h2>Last move</h2>
        ${lastMoveBody}
      </section>
      <section>
        <h2>Cascade</h2>
        <p>${escapeHtml(DICT.omega.word)} ${escapeHtml(String(cascade.rejected.omega))} · ${escapeHtml(DICT.v_sem.word)} ${escapeHtml(String(cascade.rejected.v_sem))} · ${escapeHtml(DICT.smoke.word)} ${escapeHtml(String(cascade.rejected.smoke))}</p>
        <p class="panel-note">llm_calls ${escapeHtml(String(cascade.llmCalls))} · runs ${escapeHtml(String(cascade.runs))}</p>
      </section>
    </div>
    <div class="dashboard-grid">
      <section>
        <h2>Live</h2>
        ${buildNowRunningPanel(state, nowMs)}
      </section>
      <section>
        <h2>Score vs current best</h2>
        ${buildScorePanel(state)}
      </section>
      <section>
        <h2>What happened</h2>
        ${buildEventsPanel(state)}
      </section>
      <section>
        <h2>Stopping</h2>
        ${buildStoppingPanel(state)}
      </section>
      <section>
        <h2>Papers</h2>
        ${buildPaperTickerPanel(state)}
      </section>
    </div>
  `;
  if (prevScrollTop > 0) {
    const nextScrollEl = requireView().querySelector(".event-scroll");
    if (nextScrollEl) nextScrollEl.scrollTop = prevScrollTop;
  }
  ensureDashboardRungFetch();
}

// --- Protocol: read-only, all data from state.run.protocol. Two visually
// distinct tiers — hashed (defines comparability) vs. not-hashed (bounds this
// run only) — per Handoff_app.md. No control here may change a run. ---


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
  const hover = display === str ? "click to copy" : `${str} — click to copy`;
  return `<span class="hash-value" data-copy="${escapeAttr(str)}" title="${escapeAttr(hover)}">${escapeHtml(display)}</span>`;
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
      <div class="protocol-scroll">
        <table class="metrics">
          <thead><tr><th>Metric</th><th>Population</th><th>Positive</th><th>Required output</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
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

// Published values can be per-metric maps — route them through
// fmtPublished so an object never reaches String() (fix list item 5).
function renderPublished(value) {
  if (value === null || value === undefined) return chip("not set", "chip-null");
  return escapeHtml(fmtPublished(value));
}

function buildBaselineBlock(baseline) {
  const published = baseline?.published || {};
  const reproduced = baseline?.reproduced || {};
  const metricNames = [...new Set([...Object.keys(published), ...Object.keys(reproduced)])];
  const rows = metricNames
    .map(
      (name) => `<tr>
        <td>${escapeHtml(name)}</td>
        <td>${renderPublished(published[name])}</td>
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
          ? `<div class="protocol-scroll">
               <table class="metrics">
                 <thead><tr><th>Metric</th><th>Published</th><th>Reproduced</th></tr></thead>
                 <tbody>${rows}</tbody>
               </table>
             </div>`
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
    requireView().innerHTML = `<p class="waiting">Waiting for run_started…</p>`;
    return;
  }
  requireView().innerHTML = buildHashedTier(protocol) + buildNotHashedTier(protocol.run);
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
  requireView().addEventListener("click", (e) => {
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

// --- Run tree: recursive render over buildTree(state) (tree.js — pure, no
// DOM). Handoff_app.md, "Task 7". The dossier beside the tree is a
// placeholder; building it is Task 8, explicitly out of scope here. ---

// "#/run/<id>" -> "<id>" (as a string; node ids from node_created come over
// the wire as numbers, but plain-object property access coerces either way,
// so state.nodes[selectedId] and String(node.id) === selectedId both work
// without further parsing). initRunTreeClicks encodes the id with
// encodeURIComponent when it builds the hash, so this must decode it back —
// guarded, since a hand-edited or corrupted hash can carry a malformed
// escape sequence that would otherwise throw out of the router. "#/run"
// alone -> null (nothing selected yet).
function selectedRunNodeId(path) {
  const m = /^run\/(.+)$/.exec(path);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch (_) {
    return m[1]; // malformed escape sequence: fall back to the raw segment
  }
}

// Render key for the "run" route: only the things this screen actually
// displays (which nodes exist, each one's verbatim state, the incumbent,
// which node is selected, and that selected node's dossier contents) should
// force a rebuild. Everything else that flows through the store —
// heartbeats, measurement ticks, cache lookups — must not re-render the
// tree. Same pattern as Protocol's key (Handoff_app.md, batch 1), just keyed
// on Run's own slice of state plus the selected id, since selection lives in
// the URL, not in state.
//
// The trap this closes: a new verdict, failure, recovery or rule trip does
// not always change the node's `state` (e.g. an "inconclusive" screen
// verdict on an already-"screening" node, or a rule_trip that doesn't
// retarget the node's state). nodeSig alone would then stay identical and
// renderRoute's early-return would leave the dossier showing stale data.
// Counting the selected node's own dossier-relevant arrays (via buildDossier
// — dossier.js already does the id-type-safe ev.node filtering) closes that
// gap without keying on state.lastSeq, which changes on every heartbeat and
// would defeat the whole point of a key.
function runRouteKey(state, path) {
  const nodeSig = state.nodeOrder
    .map((id) => `${id}:${state.nodes[id] ? state.nodes[id].state : "?"}`)
    .join(",");
  const selectedId = selectedRunNodeId(path);
  const dossier = selectedId != null ? buildDossier(state, selectedId) : null;
  const selectedSig = dossier
    ? `${dossier.verdicts.length}:${dossier.node.failures.length}:${dossier.node.recoveries.length}:${dossier.node.ruleTrips.length}`
    : "none";
  return `${path}|${nodeSig}|${state.incumbent}|${selectedSig}`;
}

function renderTreeNode(entry, state, selectedId) {
  const { node, children, orphan, plainState, onBestPath, dimmed, loops, edgeLabel } =
    entry;
  const isIncumbent =
    state.incumbent != null && String(state.incumbent) === String(node.id);
  const isSelected =
    selectedId != null && String(selectedId) === String(node.id);
  const isLive = ["screening", "running", "replicating", "debugging"].includes(
    node.state,
  );
  const classes = ["tree-node"];
  if (isSelected) classes.push("tree-node-selected");
  if (orphan) classes.push("tree-node-orphan");
  if (dimmed) classes.push("tree-node-dimmed");
  if (onBestPath) classes.push("tree-node-best");
  if (isLive) classes.push("tree-node-live");
  const hypHtml =
    node.hypothesisId != null
      ? escapeHtml(String(node.hypothesisId))
      : chip("no idea id", "chip-null");
  const badges = [];
  if (isIncumbent) {
    badges.push(
      `<span class="chip chip-incumbent">◆ current best</span>`,
    );
  }
  if (orphan) badges.push(chip("orphan", "chip-null"));
  if (loops > 0) {
    badges.push(
      `<span class="tree-loop-badge">retry ${escapeHtml(String(loops))}</span>`,
    );
  }
  if (isLive) {
    badges.push(`<span class="tree-live-dot" aria-label="live"></span>`);
  }
  const edgeHtml =
    edgeLabel != null
      ? `<span class="tree-edge-label">${escapeHtml(edgeLabel)}</span>`
      : "";
  const childrenHtml = children.length
    ? `<ul class="tree-children${onBestPath ? " tree-children-best" : ""}">${children
        .map((c) => renderTreeNode(c, state, selectedId))
        .join("")}</ul>`
    : "";
  return `
    <li>
      ${edgeHtml}
      <div class="${classes.join(" ")}" data-node-id="${escapeAttr(String(node.id))}">
        <span class="tree-node-id">#${escapeHtml(String(node.id))}</span>
        <span class="tree-node-hyp">idea ${hypHtml}</span>
        <span class="tree-node-kind">${escapeHtml(moveLabel(node.kind).word)}</span>
        <span class="tree-node-state">${escapeHtml((plainState && plainState.word) || stateLabel(node.state).word)}</span>
        ${badges.join(" ")}
      </div>
      ${childrenHtml}
    </li>
  `;
}

// --- Node dossier: the panel beside the tree, for the selected node
// (dossier.js — pure, no DOM). Handoff_app.md, "Task 8". Never re-derives
// band logic: threshold/thresholdLabel/side come straight from
// dossier.js's verdictReading; the "why" text for a missing threshold comes
// straight from band.js's own verdictAnnotation, same as the Score panel. ---

function fmtSeedValues(arr) {
  if (!Array.isArray(arr) || !arr.length) return chip("none", "chip-null");
  return arr
    .map((n) => (typeof n === "number" && Number.isFinite(n) ? fmtNum(n) : escapeHtml(String(n))))
    .join(", ");
}

function renderDossierHeader(node) {
  const hypHtml =
    node.hypothesisId != null
      ? escapeHtml(String(node.hypothesisId))
      : chip("no idea id", "chip-null");
  const kindLabel = moveLabel(node.kind).word;
  const state = stateLabel(node.state);
  return `
    <div class="dossier-header">
      <span class="dossier-id">#${escapeHtml(String(node.id))}</span>
      <span class="dossier-hyp">idea ${hypHtml}</span>
      <span class="dossier-kind">${escapeHtml(kindLabel)}</span>
      ${chipHtml(state, chipStateModifier(node.state))}
    </div>
  `;
}

function renderDossierHistory(node) {
  const history = Array.isArray(node.stateHistory) ? node.stateHistory : [];
  if (!history.length) return `<p class="panel-empty">no state history</p>`;
  const rows = history
    .map(
      (h) =>
        `<li>${escapeHtml(stateLabel(h.state).word)} <span class="dossier-dim">— seq ${escapeHtml(String(h.seq))} — ${escapeHtml(String(h.t))}</span></li>`,
    )
    .join("");
  return `<ol class="dossier-history">${rows}</ol>`;
}

// side is verdictReading's own "above"/"below"/"at" — "at" passes in both
// screen_verdict (>=) and replicate_verdict (<), per band.js's comment on
// the boundary. Rendered verbatim, not relabelled.
function sideLabel(side) {
  if (side === "above") return "above";
  if (side === "below") return "below";
  if (side === "at") return "at (passes)";
  return "—";
}

function renderVerdictEntry({ verdict, reading }) {
  let thresholdHtml;
  if (reading.threshold != null) {
    thresholdHtml = `<div>threshold: ${fmtNum(reading.threshold)} (${escapeHtml(reading.thresholdLabel)}) — side: ${escapeHtml(sideLabel(reading.side))}</div>`;
  } else {
    // Rule 2/3 of the band contract (Handoff_app.md): a missing rung or a
    // legacy/none band shape never gets a fabricated threshold — say which
    // comparison is unavailable and why, via band.js's own verdictAnnotation,
    // never invent one here.
    const { reason } = verdictAnnotation(verdict);
    thresholdHtml = `<div class="dossier-no-threshold">no threshold available — ${escapeHtml(reason || DICT.bandMissingReason.word)}</div>`;
  }
  const deltaMeanHtml =
    typeof verdict.delta_mean === "number" && Number.isFinite(verdict.delta_mean)
      ? `<div>Δ mean: ${fmtNum(verdict.delta_mean)} ${stampHtml("measured")}</div>`
      : `<div>Δ mean: ${chip("not reported", "chip-null")}</div>`;
  const rungHtml = `<div>test: ${verdict.rung != null ? escapeHtml(rungLabel(verdict.rung).word) : chip("not reported", "chip-null")}</div>`;
  const deltaPerSeedHtml = `<div>Δ per seed: ${fmtSeedValues(verdict.delta_per_seed)}</div>`;
  const attributionHtml =
    verdict.attribution != null
      ? `<div>${escapeHtml(attributionLabel(verdict.attribution))}</div>`
      : "";
  // A leak trip is the most important thing a node can carry — visually
  // prominent, not just another line item (Handoff_app.md, "Task 8").
  const ruleTripsHtml =
    Array.isArray(verdict.rule_trips) && verdict.rule_trips.length
      ? `<div class="dossier-rule-trip">⚠ rule trips: ${verdict.rule_trips.map((r) => escapeHtml(String(r))).join(", ")}</div>`
      : "";
  return `
    <li class="dossier-verdict">
      <div class="dossier-verdict-head">
        <span class="dossier-verdict-state">${escapeHtml(stateLabel(verdict.state).word)}</span>
        <span class="dossier-dim">metric ${escapeHtml(String(verdict.metric ?? "?"))} · seq ${escapeHtml(String(verdict.seq ?? "?"))} · ${escapeHtml(String(verdict.t ?? ""))}</span>
      </div>
      ${rungHtml}
      ${deltaMeanHtml}
      ${thresholdHtml}
      ${deltaPerSeedHtml}
      ${attributionHtml}
      ${ruleTripsHtml}
    </li>
  `;
}

function renderDossierVerdicts(verdicts) {
  if (!verdicts.length) return `<p class="panel-empty">no decisions yet</p>`;
  return `<ul class="dossier-verdicts">${verdicts.map(renderVerdictEntry).join("")}</ul>`;
}

function renderReliabilityList(items, formatOne) {
  if (!items.length) return `<p class="panel-empty">none</p>`;
  return `<ul class="dossier-reliability">${items.map((ev) => `<li>${formatOne(ev)}</li>`).join("")}</ul>`;
}

function renderDossierReliability(node) {
  const failures = Array.isArray(node.failures) ? node.failures : [];
  const recoveries = Array.isArray(node.recoveries) ? node.recoveries : [];
  const ruleTrips = Array.isArray(node.ruleTrips) ? node.ruleTrips : [];
  const failuresHtml = renderReliabilityList(failures, (ev) =>
    escapeHtml(`${ev.class ?? "?"} — ${ev.summary ?? ""}`),
  );
  const recoveriesHtml = renderReliabilityList(recoveries, (ev) =>
    escapeHtml(`${ev.action ?? "?"} (${ev.class ?? "?"}) — ${ev.summary ?? ""}`),
  );
  const ruleTripsHtml = ruleTrips.length
    ? `<ul class="dossier-reliability">${ruleTrips
        .map(
          (ev) =>
            `<li class="dossier-rule-trip">⚠ ${escapeHtml(`${ev.rule ?? "?"} — ${ev.summary ?? ""}`)}</li>`,
        )
        .join("")}</ul>`
    : `<p class="panel-empty">none</p>`;
  return `
    <div class="dossier-section">
      <h3>Failures</h3>
      ${failuresHtml}
    </div>
    <div class="dossier-section">
      <h3>Recoveries</h3>
      ${recoveriesHtml}
    </div>
    <div class="dossier-section">
      <h3>Rule trips</h3>
      ${ruleTripsHtml}
    </div>
  `;
}

function renderDossierScores(node) {
  const scores = node.scores && typeof node.scores === "object" ? node.scores : {};
  const metricNames = Object.keys(scores);
  if (!metricNames.length) return `<p class="panel-empty">no scores yet</p>`;
  const rows = metricNames
    .map((m) => `${kv(m, fmtSeedValues(scores[m]))}`)
    .join("");
  return `<dl class="kv">${rows}</dl>`;
}

function renderAttemptTrailItem(row) {
  switch (row.kind) {
    case "paper":
      return `<a href="${escapeAttr(row.href)}">${escapeHtml(row.title || "paper")}</a>`;
    case "idea": {
      const gain =
        row.expectedGain == null ? "—" : fmtDelta(row.expectedGain);
      return `${escapeHtml(row.pattern || "idea")} · expected ${escapeHtml(gain)}`;
    }
    case "free-checks":
      return `free checks passed${row.levels?.length ? ` (${escapeHtml(row.levels.join(", "))})` : ""}`;
    case "quick-test":
    case "repeat-test":
    case "hidden-check": {
      const label =
        row.kind === "quick-test"
          ? "quick test"
          : row.kind === "repeat-test"
            ? "repeat test"
            : "hidden check";
      const score = row.score == null ? "—" : fmtScore(row.score);
      const bar =
        Array.isArray(row.band) && row.band.length === 2
          ? ` noise bar ${escapeHtml(fmtScore(row.band[0]))}–${escapeHtml(fmtScore(row.band[1]))}`
          : "";
      return `${label} ${escapeHtml(score)}${bar}`;
    }
    case "decision":
      return escapeHtml(row.text || "");
    case "note":
      return escapeHtml(row.text || "");
    default:
      return "";
  }
}

function renderAttemptTrail(state, nodeId) {
  const rows = buildAttemptTrail(state, nodeId);
  if (!rows.length) return "";
  const items = rows
    .map((row) => `<li>${renderAttemptTrailItem(row)}</li>`)
    .join("");
  return `<ol class="trail attempt-trail">${items}</ol>`;
}

function renderDossier(dossier, journey = null, trailHtml = "", claimHtml = "", receipt = null) {
  const { node, verdicts } = dossier;
  const strip = journey ? journeyStripHtml(journey, receipt) : "";
  return `
    ${strip}
    ${trailHtml}
    ${claimHtml}
    ${renderDossierHeader(node)}
    <div class="dossier-section">
      <h3>History</h3>
      ${renderDossierHistory(node)}
    </div>
    <div class="dossier-section">
      <h3>Decisions</h3>
      ${renderDossierVerdicts(verdicts)}
    </div>
    ${renderDossierReliability(node)}
    <div class="dossier-section">
      <h3>Scores</h3>
      ${renderDossierScores(node)}
    </div>
    <div class="dossier-section">
      <h3>Seeds</h3>
      <p>${fmtSeedValues(node.seeds)}</p>
    </div>
  `;
}

function renderMoveTrail(state) {
  const rows = buildMoveTrail(state);
  if (!rows.length) return `<p class="panel-empty">no moves yet</p>`;
  const items = rows
    .map((row) => {
      const body =
        row.href != null
          ? `<a href="${escapeAttr(row.href)}">${escapeHtml(row.text)}</a>`
          : escapeHtml(row.text);
      return `<li>${body}</li>`;
    })
    .join("");
  return `<ol class="trail move-trail">${items}</ol>`;
}

function renderRun(state, path) {
  const selectedId = selectedRunNodeId(path);
  const roots = buildTree(state);
  const treeHtml = roots.length
    ? `<ul class="tree-root">${roots.map((r) => renderTreeNode(r, state, selectedId)).join("")}</ul>`
    : `<p class="panel-empty">no attempts yet</p>`;

  // An unknown node id must render "no such node" inside the Run screen —
  // never a blank page, never a fall-through to Dashboard.
  let dossierHtml;
  if (selectedId == null) {
    dossierHtml = `<p class="panel-empty">select an attempt</p>`;
  } else if (!Object.prototype.hasOwnProperty.call(state.nodes, selectedId)) {
    dossierHtml = `<p class="panel-empty">no such attempt</p>`;
  } else {
    const dossier = buildDossier(state, selectedId);
    const journey = buildJourney(state, selectedId);
    const trailHtml = renderAttemptTrail(state, selectedId);
    const claimHtml = claimCardHtml(buildClaimCard(state, selectedId));
    const receipt = buildReceipt(state, cachedContract, selectedId);
    ensureContract();
    dossierHtml = dossier
      ? renderDossier(dossier, journey, trailHtml, claimHtml, receipt)
      : `<p class="panel-empty">no such attempt</p>`;
  }

  requireView().innerHTML = `
    <div class="run-grid">
      <section class="run-tree-panel">
        <h2>Attempts</h2>
        ${renderMoveTrail(state)}
        ${treeHtml}
      </section>
      <section class="run-dossier-panel">
        <h2>Attempt</h2>
        ${dossierHtml}
      </section>
    </div>
  `;
}

// Delegated on #view (a stable element across renders — only its innerHTML
// changes), same pattern as initClickToCopy, so this is wired once in
// main() rather than re-attached on every render.
function initRunTreeClicks() {
  requireView().addEventListener("click", (e) => {
    const target = e.target.closest(".tree-node[data-node-id]");
    if (!target) return;
    location.hash = `#/run/${encodeURIComponent(target.dataset.nodeId)}`;
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

function renderRunStateSlot(run, live) {
  let colorClass = "dot-grey";
  let text = "waiting";
  if (live.status === "stalled") {
    // Item 7: a killed run has no run_ended event, so run.status says
    // "running" forever. Silence is the honest signal.
    colorClass = "dot-amber";
    text = stalledText(live.quietMs);
  } else if (run.status === "running") {
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

function renderElapsedBudgetSlot(run, live, lastSignalAt) {
  const el = document.getElementById("hdr-elapsed-budget");
  if (!run.startedAt) {
    el.textContent = "not started";
    return;
  }
  // Item 7: on a stalled run the client-side clock must stop — ticking
  // "elapsed" past the last signal claims work that is not happening. Freeze
  // at the moment the run was last heard from.
  let end;
  if (run.status === "ended" && run.endedAt) end = new Date(run.endedAt);
  else if (live.status === "stalled" && lastSignalAt) {
    end = new Date(lastSignalAt);
  } else end = new Date();
  const elapsed = formatDuration(end - new Date(run.startedAt));
  const budgetH = run.protocol?.run?.budget?.wall_clock_h;
  if (budgetH == null) {
    el.innerHTML = `${escapeHtml(elapsed)} ${chip("no budget set", "chip-null")}`;
  } else {
    el.textContent = `${elapsed} / ${fmtNum(budgetH)}h budget`;
  }
}

function renderHeader(state) {
  const live = liveness(state.run, state.lastSignalAt, Date.now());
  renderRunStateSlot(state.run, live);
  renderSubmissionSlot(state);
  renderSpendSlot();
  renderInterventionsSlot(state);
  renderElapsedBudgetSlot(state.run, live, state.lastSignalAt);
}

function renderStyleguide() {
  requireView().innerHTML = `
    <div class="styleguide">
      <h2>Styleguide</h2>
      <section class="card">
        <p>Card — surface, hairline, 10px radius, 24px padding.</p>
      </section>
      <div class="stat">
        <span class="stat-value">0.6041</span>
        <span class="stat-caption">score</span>
        <span class="stat-src" title="monitors.primary">${escapeHtml(DICT.scoreSource.word)}</span>
      </div>
      <div class="chip-row">
        <span class="chip-state chip-state--accepted">accepted</span>
        <span class="chip-state chip-state--declined">declined</span>
        <span class="chip-state chip-state--retrying">retrying</span>
        <span class="chip-state chip-state--shelved">shelved</span>
        <span class="chip-state chip-state--disqualified">disqualified</span>
        <span class="chip-state chip-state--crashed">crashed</span>
        <span class="chip-state chip-state--live">live</span>
      </div>
      <p class="empty">nothing here yet</p>
      <div class="doc">
        <p>Doc column — 68 characters, 16px at 1.7. Later pages (game plan, summary) copy this width.</p>
      </div>
      <ol class="trail">
        <li>Paper read</li>
        <li>Idea queued</li>
        <li>Attempt built</li>
      </ol>
    </div>
  `;
}

let memoryFetchGen = 0;

function renderMemory(state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading what the run has learned…</p>`;
  const path = currentRoutePath();
  const gen = ++memoryFetchGen;
  if (!runId) {
    view.innerHTML = memoryPageHtml(
      buildMemory(state, { available: false, reason: DICT.memoryEmpty.word }),
    );
    return;
  }
  fetch(`/runs/${runId}/feedback`)
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== memoryFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = memoryPageHtml(buildMemory(state, payload));
    })
    .catch(() => {
      if (gen !== memoryFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = memoryPageHtml(
        buildMemory(state, { available: false, reason: DICT.memoryEmpty.word }),
      );
    });
}

let rulebookFetchGen = 0;

function renderRulebook(state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading the rules…</p>`;
  const path = currentRoutePath();
  const gen = ++rulebookFetchGen;
  fetch("/contract")
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== rulebookFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = rulebookPageHtml(buildRulebook(payload, state));
    })
    .catch(() => {
      if (gen !== rulebookFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = rulebookPageHtml(
        buildRulebook({ available: false, reason: DICT.rulebookUnavailable.word }, state),
      );
    });
}

let briefFetchGen = 0;

function renderBrief(_state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading game plan…</p>`;
  const path = currentRoutePath();
  const gen = ++briefFetchGen;
  if (!runId) {
    view.innerHTML = `<p class="empty">game plan unavailable</p>`;
    return;
  }
  fetch(`/runs/${runId}/brief`)
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== briefFetchGen) return;
      if (currentRoutePath() !== path) return;
      const vm = buildBrief(payload);
      if (!vm) {
        view.innerHTML = `<p class="empty">game plan unavailable</p>`;
        return;
      }
      view.innerHTML = briefPageHtml(vm);
    })
    .catch(() => {
      if (gen !== briefFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = `<p class="empty">game plan unavailable</p>`;
    });
}

let libraryFetchGen = 0;

function renderLibrary(_state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading library…</p>`;
  const path = currentRoutePath();
  const gen = ++libraryFetchGen;
  fetch("/papers/manifest")
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== libraryFetchGen) return;
      if (currentRoutePath() !== path) return;
      const papers =
        payload?.available === true && Array.isArray(payload.papers)
          ? payload.papers
          : [];
      view.innerHTML = libraryPageHtml(buildLibrary(store.getState(), papers));
    })
    .catch(() => {
      if (gen !== libraryFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = `<p class="empty">library unavailable</p>`;
    });
}

function renderIdeas(state) {
  const vm = buildIdeas(state);
  requireView().innerHTML = vm
    ? ideasPageHtml(vm)
    : `<p class="empty">no ideas yet</p>`;
}

function fetchAudit(label, url, build, html) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading ${label}…</p>`;
  const path = currentRoutePath();
  if (!runId) {
    view.innerHTML = `<p class="empty">${label} unavailable</p>`;
    return;
  }
  fetch(url)
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (currentRoutePath() !== path) return;
      const vm = build(payload);
      view.innerHTML = vm ? html(vm) : `<p class="empty">${label} unavailable</p>`;
    })
    .catch(() => {
      if (currentRoutePath() !== path) return;
      view.innerHTML = `<p class="empty">${label} unavailable</p>`;
    });
}

function renderDoubleChecks() {
  fetchAudit(
    "double-checks",
    `/runs/${runId}/audit/replication`,
    buildDoubleChecks,
    doubleChecksPageHtml,
  );
}

function renderSpend() {
  fetchAudit("spend", `/runs/${runId}/audit/cost`, buildSpend, spendPageHtml);
}

function renderStability() {
  fetchAudit(
    "stability",
    `/runs/${runId}/audit/reliability`,
    buildStability,
    stabilityPageHtml,
  );
}

let reportFetchGen = 0;

function renderReport(_state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading summary…</p>`;
  const path = currentRoutePath();
  const gen = ++reportFetchGen;
  if (!runId) {
    view.innerHTML = `<p class="empty">summary unavailable</p>`;
    return;
  }
  Promise.all([
    fetch(`/runs/${runId}/report`).then(flagStaleServer).then((res) => res.json()),
    fetch(`/runs/${runId}/audit/monitors`)
      .then(flagStaleServer).then((res) => res.json())
      .catch(() => null),
  ])
    .then(([reportPayload, monitorsPayload]) => {
      if (gen !== reportFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = reportPageHtml(
        buildReport(reportPayload),
        buildReportHero(monitorsPayload),
      );
    })
    .catch(() => {
      if (gen !== reportFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = `<p class="empty">summary unavailable</p>`;
    });
}

let monitorsFetchGen = 0;

function renderMonitors(_state) {
  const view = requireView();
  view.innerHTML = `<p class="panel-empty">loading monitors…</p>`;
  const path = currentRoutePath();
  const gen = ++monitorsFetchGen;
  if (!runId) {
    view.innerHTML = `<p class="panel-empty">monitors unavailable</p>`;
    return;
  }
  fetch(`/runs/${runId}/audit/monitors`)
    .then(flagStaleServer).then((res) => res.json())
    .then((payload) => {
      if (gen !== monitorsFetchGen) return;
      if (currentRoutePath() !== path) return;
      const vm = buildMonitors(payload);
      if (!vm) {
        view.innerHTML = `<p class="panel-empty">monitors payload unusable</p>`;
        return;
      }
      view.innerHTML = wallHtml(buildWall(payload)) + renderMonitorsView(vm);
    })
    .catch(() => {
      if (gen !== monitorsFetchGen) return;
      if (currentRoutePath() !== path) return;
      view.innerHTML = `<p class="panel-empty">monitors unavailable</p>`;
    });
}

function renderMonitorsView(vm) {
  const numbers = vm.numbers
    .map(
      (row) =>
        `<li><span>${escapeHtml(row.label)}</span> ${escapeHtml(row.text)} ${stampHtml("measured")}` +
        ` <span class="panel-note">${escapeHtml(row.source)}</span></li>`,
    )
    .join("");
  const gaps = vm.gap.points.length
    ? vm.gap.points
        .map(
          (p) =>
            `<li>node ${escapeHtml(String(p.node))} gap ${escapeHtml(String(p.gap))}</li>`,
        )
        .join("")
    : `<p class="panel-empty">no ${escapeHtml(DICT.oracle.word)} gaps</p>`;
  const seeds = vm.seedEmpty
    ? `<p class="panel-empty">no seed-consistency rows</p>`
    : `<ul>${vm.seedConsistency
        .map(
          (row) =>
            `<li>node ${escapeHtml(String(row.node))} ${escapeHtml(row.text)}</li>`,
        )
        .join("")}</ul>`;
  const alarm = vm.gap.alarm ? "alarm" : "quiet";
  return `
    <div class="dashboard-grid">
      <section>
        <h2>Headline</h2>
        <ul>${numbers}</ul>
      </section>
      <section>
        <h2>${escapeHtml(DICT.oracleGapHeading.word)} (${escapeHtml(alarm)})</h2>
        ${vm.gap.points.length ? `<ul>${gaps}</ul>` : gaps}
      </section>
      <section>
        <h2>Seed consistency</h2>
        ${seeds}
      </section>
      <section>
        <h2>${escapeHtml(DICT.rungHeading.word)}</h2>
        <p>${escapeHtml(vm.rung.level)}</p>
        <p class="panel-note">${escapeHtml(vm.rung.reason)}</p>
      </section>
    </div>
  `;
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
  { hash: "brief", render: renderBrief },
  { hash: "the-rules", render: renderRulebook },
  { hash: "learned", render: renderMemory },
  { hash: "research", render: renderLibrary },
  { hash: "hypotheses", render: renderIdeas },
  // "run" matches both "#/run" and "#/run/<nodeId>" — ROUTES used to match
  // hash strings exactly, so "#/run/3" matched nothing and fell through to
  // the DEFAULT_ROUTE (Dashboard). match() below is what fixes that; hash
  // stays "run" for both so the sidebar highlight and key still work as a
  // single route. key includes the selected id (from path, not state) so
  // clicking a different node still forces a render despite the hash
  // staying "run".
  {
    hash: "run",
    match: (path) => path === "run" || path.startsWith("run/"),
    render: renderRun,
    key: runRouteKey,
  },
  { hash: "audit/replication", render: renderDoubleChecks },
  { hash: "audit/cost", render: renderSpend },
  { hash: "audit/reliability", render: renderStability },
  { hash: "audit/monitors", render: renderMonitors },
  { hash: "report", render: renderReport },
  { hash: "styleguide", render: renderStyleguide },
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
// Tracks the last PATH (not hash) painted into the pane, so switching tabs —
// or attempts within #/run/<id>, where the hash stays "run" — puts the pane
// back at the top, while store ticks re-rendering the same path never touch
// the reader's scroll position.
let lastScrolledPath = null;

function resetPaneScroll(path) {
  if (path === lastScrolledPath) return;
  lastScrolledPath = path;
  const pane = document.getElementById("pane");
  if (pane) pane.scrollTop = 0;
}

function renderRoute() {
  const path = currentRoutePath();
  const redirect = REDIRECTS[path];
  if (redirect) {
    location.hash = `#/${redirect}`; // hashchange re-invokes renderRoute with the resolved path
    return;
  }
  const route =
    ROUTES.find((r) => (r.match ? r.match(path) : r.hash === path)) ||
    ROUTES.find((r) => r.hash === DEFAULT_ROUTE);
  highlightSidebar(route.hash);
  const state = store.getState();
  if (route.key) {
    const key = route.key(state, path);
    if (lastRenderedHash === route.hash && key === lastRenderedKey) return;
    lastRenderedKey = key;
  }
  lastRenderedHash = route.hash;
  route.render(state, path);
  resetPaneScroll(path);
  applyTourHighlight();
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

// Item 8: a tab opened before the run directory exists gets a 404 on the
// stream; EventSource does NOT auto-retry a failed connection, so without
// these handlers the page froze at "not started" forever. Reconnect with
// exponential backoff; the attempt counter resets on any message, and the
// since-cursor means each reconnect refolds exactly the events the reducer
// has not seen — frozen panels come alive as soon as the run appears.
let eventsAttempt = 0;
let heartbeatAttempt = 0;

function connectEvents() {
  if (eventsSource) eventsSource.close();
  eventsSource = new EventSource(`/runs/${runId}/events?since=${eventsSince}`);
  eventsSource.onmessage = (raw) => {
    eventsAttempt = 0;
    const ev = JSON.parse(raw.data);
    store.applyEvent(ev);
    eventsSince = ev.seq;
  };
  eventsSource.onerror = () => {
    eventsSource.close();
    setTimeout(connectEvents, backoffDelay(eventsAttempt));
    eventsAttempt += 1;
  };
}

function connectHeartbeat() {
  if (heartbeatSource) heartbeatSource.close();
  heartbeatSource = new EventSource(
    `/runs/${runId}/heartbeat?since=${heartbeatSince}`,
  );
  heartbeatSource.onmessage = (raw) => {
    heartbeatAttempt = 0;
    const ev = JSON.parse(raw.data);
    store.applyEvent(ev);
    heartbeatSince = ev.seq;
  };
  heartbeatSource.onerror = () => {
    heartbeatSource.close();
    setTimeout(connectHeartbeat, backoffDelay(heartbeatAttempt));
    heartbeatAttempt += 1;
  };
}

// Item 8's second freeze path: /runs empty (or the server briefly away)
// used to throw straight out of main() — the app died before its first
// paint and never looked again. Keep asking with the same backoff.
async function resolveRunId() {
  const params = new URLSearchParams(location.search);
  const fromQuery = params.get("run");
  if (fromQuery) return fromQuery;
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch("/runs");
      const runs = await res.json();
      if (runs.length) return runs[0].run_id;
      metaEl().textContent = "waiting for the first run to appear…";
    } catch (_) {
      metaEl().textContent = "waiting for the server…";
    }
    await new Promise((tick) => setTimeout(tick, backoffDelay(attempt)));
  }
}

function switchRun(nextRunId) {
  runId = nextRunId;
  eventsSince = 0;
  heartbeatSince = 0;
  store.replaceState(initial());
  connectEvents();
  connectHeartbeat();
}

// Item 9: the run picker. Rebuilt only when the option labels actually
// change, so an open dropdown is not wiped mid-choice by the 2s poll.
let pickerSignature = null;

function renderRunPicker(rows) {
  const el = document.getElementById("hdr-run-picker");
  if (!el) return;
  const nowMs = Date.now();
  const options = rows.map((row) => ({
    id: row.run_id,
    label: runPickerLabel(row, nowMs),
  }));
  const signature = `${options.map((o) => `${o.id}|${o.label}`).join("\n")}@${runId}`;
  if (signature === pickerSignature) return;
  pickerSignature = signature;
  el.innerHTML = options
    .map(
      (o) =>
        `<option value="${escapeAttr(o.id)}"${o.id === runId ? " selected" : ""}>${escapeHtml(o.label)}</option>`,
    )
    .join("");
}

function initRunPicker() {
  const el = document.getElementById("hdr-run-picker");
  if (!el) return;
  el.addEventListener("change", () => {
    const picked = el.value;
    if (!picked || picked === runId) return;
    // An explicit choice pins the run in the URL — refresh keeps it, and
    // the newest-run follower stops switching underneath the reader.
    const params = new URLSearchParams(location.search);
    params.set("run", picked);
    history.replaceState(null, "", `?${params}${location.hash}`);
    switchRun(picked);
  });
}

function followNewestRun() {
  setInterval(async () => {
    try {
      const res = await fetch("/runs");
      const runs = await res.json();
      if (!runs.length) return;
      renderRunPicker(runs);
      const pinned = new URLSearchParams(location.search).get("run");
      // Default to the newest run only while nothing is pinned by the URL.
      if (!pinned && runs[0].run_id !== runId) {
        switchRun(runs[0].run_id);
      }
    } catch (_) {
      /* server away; try again next tick */
    }
  }, 2000);
}

let tourIndex = 0;
let tourOpen = false;

function tourAnchorEl(anchor) {
  if (!anchor) return null;
  if (anchor.startsWith("data-")) return document.querySelector(`[${anchor}]`);
  return document.getElementById(anchor) || document.querySelector(`.${anchor}`);
}

function clearTourHighlight() {
  for (const el of document.querySelectorAll(".tour-spotlight")) {
    el.classList.remove("tour-spotlight");
  }
}

// One pane-scroll per step: renderRoute re-applies the highlight on every
// store tick, and re-centering each time would fight the reader. The guard
// resets whenever drawTour moves to another step — and stays unset while the
// anchor hasn't rendered yet, so a target that streams in late (e.g. the
// journey strip right after its attempt appears) still gets scrolled to.
let tourScrolledFor = null;

function scrollTourTargetIntoPane(el) {
  const pane = document.getElementById("pane");
  if (!pane || !pane.contains(el)) return;
  const paneBox = pane.getBoundingClientRect();
  const box = el.getBoundingClientRect();
  // Viewport-relative rects survive the scroll-locked body; never add
  // window scroll offsets on top (the body no longer scrolls — V7's window
  // assumptions are exactly what broke here).
  const target = paneScrollTarget({
    paneTop: paneBox.top,
    paneHeight: pane.clientHeight,
    paneScrollTop: pane.scrollTop,
    elTop: box.top,
    elHeight: box.height,
  });
  if (target != null) pane.scrollTo({ top: target });
}

function applyTourHighlight() {
  clearTourHighlight();
  if (!tourOpen) return;
  const stop = TOUR_STOPS[tourIndex];
  const el = tourAnchorEl(stop.anchor);
  if (!el) return;
  el.classList.add("tour-spotlight");
  if (tourScrolledFor !== tourIndex) {
    tourScrolledFor = tourIndex;
    scrollTourTargetIntoPane(el);
  }
}

function drawTour() {
  let el = document.getElementById("tour-overlay");
  if (!tourOpen) {
    el?.remove();
    clearTourHighlight();
    return;
  }
  if (!el) {
    el = document.createElement("div");
    el.id = "tour-overlay";
    // The fixed backdrop sits outside the pane, so wheel input over it
    // chains into the scroll-locked body and dies. Hand it to the pane —
    // the one scroll surface — so the reader can still move the page while
    // the tour is up.
    el.addEventListener(
      "wheel",
      (ev) => {
        const pane = document.getElementById("pane");
        if (pane) pane.scrollTop += ev.deltaY;
      },
      { passive: true },
    );
    document.body.appendChild(el);
  }
  const stop = TOUR_STOPS[tourIndex];
  el.innerHTML = tourOverlayHtml(stop, tourIndex, TOUR_STOPS.length);
  tourScrolledFor = null; // new draw = new step (or replay): allow one scroll
  const route = tourStopRoute(stop, store.getState());
  if (location.hash !== `#/${route}`) {
    // Setting the hash fires hashchange → renderRoute → route.render, and
    // renderRoute re-applies the highlight after the render lands — that is
    // the "await the route render before measuring" path. The rAF below only
    // covers the same-hash redraw, where no hashchange will come.
    location.hash = `#/${route}`;
  }
  requestAnimationFrame(applyTourHighlight);
}

function openTour(fromStart) {
  if (fromStart) tourIndex = 0;
  tourOpen = true;
  drawTour();
}

function dismissTour() {
  tourOpen = false;
  markTourDone(window.localStorage);
  document.getElementById("tour-overlay")?.remove();
  clearTourHighlight();
}

function tourNext() {
  if (tourIndex >= TOUR_STOPS.length - 1) {
    dismissTour();
    return;
  }
  tourIndex += 1;
  drawTour();
}

function initTour() {
  const replay = document.getElementById("tour-replay");
  replay?.addEventListener("click", () => openTour(true));
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest?.("[data-tour]");
    if (!btn) return;
    if (btn.dataset.tour === "next") tourNext();
    if (btn.dataset.tour === "skip") dismissTour();
  });
  document.addEventListener("keydown", (ev) => {
    if (!tourOpen) return;
    if (ev.key === "Escape") dismissTour();
    if (ev.key === "ArrowRight") tourNext();
    if (ev.key === "ArrowLeft" && tourIndex > 0) {
      tourIndex -= 1;
      drawTour();
    }
  });
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
    initRunTreeClicks();
    initRunPicker();
    initTour();
    initStaleServerBanner();
    runId = await resolveRunId();
    const showTour = shouldShowTour(window.localStorage);
    if (showTour) {
      tourIndex = 0;
      tourOpen = true;
      location.hash = `#/${tourStopRoute(TOUR_STOPS[0], store.getState())}`;
    } else if (!location.hash) {
      location.hash = `#/${DEFAULT_ROUTE}`;
    }
    renderApp(store.getState()); // initial paint: meta + route before first event
    if (showTour) drawTour();
    startApp({ runId });
    followNewestRun();
  } catch (err) {
    metaEl().textContent = String(err.message || err);
  }
}

main();
