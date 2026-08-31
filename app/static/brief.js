/** E2 Game-plan view model. Pure: no DOM, no fetch. */

export const INTRO = {
  goal:
    "Beat the current-best ranking model on this dataset, under a frozen " +
    "protocol, without touching the hidden test set until the run is over.",
  rules:
    "Every score on this page comes from a measured fold. The agent reads " +
    "papers, proposes ideas, builds attempts, and only an accepted attempt " +
    "that survived the hidden check counts as a win.",
};

export function buildBrief(payload) {
  if (payload == null || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  if (payload.available !== true) return null;
  if (!Array.isArray(payload.sections)) return null;
  return {
    task: payload.task ?? null,
    sections: payload.sections.map((s) => ({
      title: s && typeof s.title === "string" ? s.title : "",
      body: s && typeof s.body === "string" ? s.body : "",
    })),
  };
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function inline(s) {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

/** Mini renderer for # / ## / lists / bold. No CDN markdown library. */
export function renderMarkdown(src) {
  if (src == null) return "";
  const lines = String(src).split("\n");
  const out = [];
  let list = [];
  const flushList = () => {
    if (!list.length) return;
    out.push(
      "<ul>" + list.map((item) => `<li>${inline(item)}</li>`).join("") + "</ul>",
    );
    list = [];
  };
  for (const line of lines) {
    if (line.startsWith("## ")) {
      flushList();
      out.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      flushList();
      out.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
    } else if (/^[-*] /.test(line)) {
      list.push(line.slice(2));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  flushList();
  return out.join("");
}

export function briefPageHtml(vm) {
  const task =
    vm.task != null && String(vm.task).trim()
      ? `<p class="stat-caption">task ${escapeHtml(String(vm.task))}</p>`
      : "";
  const intro = `
    <section class="card">
      ${task}
      <h2>The goal</h2>
      <p>${escapeHtml(INTRO.goal)}</p>
      <h2>The rules</h2>
      <p>${escapeHtml(INTRO.rules)}</p>
    </section>`;
  const sections = vm.sections
    .map((s) => {
      const heading = s.title
        ? `<h2>${escapeHtml(s.title)}</h2>`
        : "";
      return `<section class="card">${heading}${renderMarkdown(s.body)}</section>`;
    })
    .join("");
  return `<div class="doc">${intro}${sections}</div>`;
}
