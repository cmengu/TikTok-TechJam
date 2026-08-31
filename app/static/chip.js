/** Pure chip HTML helper — no DOM, safe for node --test. */

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(s) {
  return escapeHtml(s).replaceAll('"', "&quot;");
}

/**
 * @param {{word: string, hint: string|null|undefined}} labelObj
 * @param {string|null|undefined} modifier chip-state--* suffix (e.g. "accepted")
 */
export function chipHtml(labelObj, modifier) {
  const word = labelObj?.word ?? "";
  const hint = labelObj?.hint;
  const modClass =
    modifier != null && modifier !== ""
      ? ` chip-state--${escapeAttr(modifier)}`
      : "";
  const hintAttr =
    hint != null && hint !== ""
      ? ` data-hint="${escapeAttr(hint)}"`
      : "";
  return `<span class="chip-state${modClass}"${hintAttr}>${escapeHtml(word)}</span>`;
}
