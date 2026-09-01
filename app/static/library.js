/** E5 Library view model. Pure: no DOM, no fetch. */

import { ideaOutcome } from "./reducer.js";
import { DICT, stateLabel } from "./copy.js";
import { escapeHtml, escapeAttr } from "./chip.js";
import { isCostBookkeeping } from "./trace.js";

export function normalize(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function scholarHref(title) {
  return (
    "https://scholar.google.com/scholar?q=" + encodeURIComponent(String(title ?? ""))
  );
}

function matchEntry(title, manifest) {
  const needle = normalize(title);
  if (!needle || !Array.isArray(manifest)) return null;
  for (const entry of manifest) {
    if (!entry || typeof entry !== "object") continue;
    const aliases = [entry.title, ...(Array.isArray(entry.match) ? entry.match : [])];
    if (aliases.some((a) => normalize(a) === needle)) return entry;
  }
  return null;
}

function actionFor(source, entry) {
  if (source?.url) return { kind: "link", href: String(source.url) };
  if (entry?.pdf) return { kind: "pdf", href: `/papers/${entry.pdf}` };
  if (entry?.url) return { kind: "link", href: String(entry.url) };
  return { kind: "search", href: scholarHref(source?.title) };
}

function ideasFor(state, source) {
  if (source?.node == null) return [];
  const node = state?.nodes?.[source.node] ?? state?.nodes?.[String(source.node)];
  if (!node?.hypothesisId) return [];
  const idea = state?.ideas?.byId?.[node.hypothesisId];
  const verdict = ideaOutcome(state, node.hypothesisId);
  return [
    {
      id: node.hypothesisId,
      pattern: idea?.pattern ?? idea?.mechanism ?? null,
      outcome: verdict?.state != null ? stateLabel(verdict.state).word : null,
    },
  ];
}

function tokensFor(source) {
  const cost = source?.cost;
  if (!cost || typeof cost !== "object") return 0;
  const inn = Number(cost.tokens_in) || 0;
  const out = Number(cost.tokens_out) || 0;
  return inn + out;
}

/**
 * buildLibrary(state, manifest) → [{ title, venue, year, one_liner, action, ideas, tokens }]
 * manifest is the papers array (not the {available, papers} wrapper).
 */
export function buildLibrary(state, manifest) {
  const all = state?.research?.sources;
  // Item 1 de-pollution: cost-bookkeeping rows are spend, not reading.
  const sources = (Array.isArray(all) ? all : []).filter(
    (s) => !isCostBookkeeping(s),
  );
  const papers = Array.isArray(manifest) ? manifest : [];

  // Corpus-first: the shelf is what the harness carries, not what one run
  // happened to open. A run that cited nothing (the researcher only proposes
  // once the queue drains) used to render an empty page even though every
  // paper and cover ships with the repo. Manifest papers are always cards;
  // the run's reading is layered on top, and a source citing a paper the
  // manifest doesn't know still gets its own card.
  const rowFor = (entry, source) => ({
    title: source?.title ?? entry?.title ?? "",
    venue: entry?.venue ?? null,
    year: entry?.year ?? null,
    one_liner: entry?.one_liner ?? null,
    action: actionFor(source, entry),
    cover: entry?.thumb ? `/papers/${entry.thumb}` : null,
    ideas: source ? ideasFor(state, source) : [],
    tokens: source ? tokensFor(source) : null,
    consulted: Boolean(source),
  });

  const claimed = new Set();
  const rows = papers.map((entry) => {
    const source = sources.find((s) => matchEntry(s?.title, [entry]) != null);
    if (source) claimed.add(source);
    return rowFor(entry, source);
  });
  for (const source of sources) {
    if (claimed.has(source)) continue;
    rows.push(rowFor(matchEntry(source?.title, papers), source));
  }
  return rows;
}



const ACTION_LABEL = { pdf: "Open PDF", link: "Read online", search: "Find it" };

// Placeholder spines carry one accent hue per venue, drawn from the design
// tokens (palette discipline: ink-ramp structure, sparse hue). Stable
// assignment: hash the venue name onto the short accent list.
const SPINE_ACCENTS = ["var(--wine)", "var(--pos)", "var(--warn)"];

function spineAccent(venue) {
  const s = String(venue ?? "");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return SPINE_ACCENTS[h % SPINE_ACCENTS.length];
}

/** Fix-list item 1, card grid: one card per paper — cover (real page-1
 * render with a title overlay strip) or a placeholder spine when no PDF
 * exists; title + venue · year + one_liner below; the whole card clicks
 * through to the PDF / arXiv page. */
export function libraryPageHtml(rows) {
  if (!rows.length) {
    return `<p class="empty">no papers yet</p>`;
  }
  const cards = rows
    .map((row) => {
      const meta = [row.venue, row.year].filter((x) => x != null).join(" · ");
      const ideaChips = row.ideas.length
        ? row.ideas
            .map(
              (idea) =>
                `<span class="chip-state">${escapeHtml(idea.pattern || idea.id)}</span>`,
            )
            .join(" ")
        : "";
      const cover = row.cover
        ? `<div class="paper-cover">
             <img src="${escapeAttr(row.cover)}" alt="" loading="lazy" />
             <span class="paper-cover-overlay">${escapeHtml(row.title)}</span>
           </div>`
        : `<div class="paper-spine" style="--spine-accent: ${spineAccent(row.venue)}">
             <span class="paper-spine-title">${escapeHtml(row.title)}</span>
             ${row.venue != null ? `<span class="paper-spine-venue">${escapeHtml(String(row.venue))}</span>` : ""}
           </div>`;
      const external = row.action.kind === "search" || row.action.kind === "link";
      return `
        <a class="paper-card" href="${escapeAttr(row.action.href)}"${external ? ' target="_blank" rel="noreferrer"' : ' target="_blank"'} title="${escapeAttr(ACTION_LABEL[row.action.kind] || "Open")}">
          ${cover}
          <div class="paper-card-body">
            <h2>${escapeHtml(row.title)}</h2>
            ${meta ? `<p class="stat-caption">${escapeHtml(meta)}</p>` : ""}
            ${row.one_liner ? `<p class="paper-blurb">${escapeHtml(row.one_liner)}</p>` : ""}
            ${ideaChips ? `<p>${ideaChips}</p>` : ""}
            ${row.consulted === false ? `<p class="paper-shelf stat-caption" title="${escapeAttr(DICT.paperOnShelf.hint)}">${escapeHtml(DICT.paperOnShelf.word)}</p>` : ""}
          </div>
        </a>`;
    })
    .join("");
  return `<div class="paper-grid">${cards}</div>`;
}
