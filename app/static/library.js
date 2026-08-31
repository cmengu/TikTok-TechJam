/** E5 Library view model. Pure: no DOM, no fetch. */

import { ideaOutcome } from "./reducer.js";

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
      outcome: verdict?.state ?? null,
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
  const sources = state?.research?.sources;
  if (!Array.isArray(sources) || sources.length === 0) return [];
  const papers = Array.isArray(manifest) ? manifest : [];
  return sources.map((source) => {
    const entry = matchEntry(source?.title, papers);
    return {
      title: source?.title ?? "",
      venue: entry?.venue ?? null,
      year: entry?.year ?? null,
      one_liner: entry?.one_liner ?? null,
      action: actionFor(source, entry),
      ideas: ideasFor(state, source),
      tokens: tokensFor(source),
    };
  });
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(s) {
  return escapeHtml(s).replaceAll('"', "&quot;");
}

const ACTION_LABEL = { pdf: "Open PDF", link: "Read online", search: "Find it" };

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
      const blurb = row.one_liner
        ? `<p>${escapeHtml(row.one_liner)}</p>`
        : "";
      return `
        <section class="card">
          <h2>${escapeHtml(row.title)}</h2>
          ${meta ? `<p class="stat-caption">${escapeHtml(meta)}</p>` : ""}
          ${blurb}
          <p><a href="${escapeAttr(row.action.href)}"${row.action.kind === "search" || row.action.kind === "link" ? ' target="_blank" rel="noreferrer"' : ""}>${escapeHtml(ACTION_LABEL[row.action.kind] || "Open")}</a></p>
          ${ideaChips ? `<p>${ideaChips}</p>` : ""}
          <p class="stat-src">${escapeHtml(String(row.tokens))} tokens</p>
        </section>`;
    })
    .join("");
  return `<div class="doc">${cards}</div>`;
}
