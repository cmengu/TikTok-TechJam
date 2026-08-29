import re, html, sys
from pathlib import Path

src = Path(sys.argv[1]); dst = src.with_suffix(".md")
s = src.read_text()
s = s.split('<div class="wrap">',1)[1]
s = re.sub(r'<style.*?</style>', '', s, flags=re.S)

def svg_placeholder(m):
    # keep the diagram's own text labels so a plain-text reader sees what it showed
    labels, seen = [], set()
    for t in re.findall(r'<text[^>]*>(.*?)</text>', m.group(0), flags=re.S):
        t = html.unescape(re.sub(r'<[^>]+>', '', t)).strip()
        t = re.sub(r'\s+', ' ', t)
        if t and t not in seen:
            seen.add(t); labels.append(t)
    body = ' · '.join(labels[:80])
    return f"\n[diagram — see the HTML/artifact version. Labels: {body}]\n" if body else "\n[diagram — see the HTML/artifact version]\n"
s = re.sub(r'<svg.*?</svg>', svg_placeholder, s, flags=re.S)

pres=[]
def keep(m):
    body = re.sub(r'</?(?:code|span)[^>]*>','',m.group(1))
    pres.append(html.unescape(body).strip('\n'))
    return f"\x00PRE{len(pres)-1}\x00"
s = re.sub(r'<pre>(.*?)</pre>', keep, s, flags=re.S)

def txt(x):                                  # strip tags; do NOT unescape yet
    return re.sub(r'[ \t]+',' ', re.sub(r'<[^>]+>','',x)).strip()
def flat(x):                                 # single-line variant for table cells / list items
    return re.sub(r'\s*\n\s*', ' ', txt(x))

s = re.sub(r'<br\s*/?>', '\n', s)            # line breaks survive (O1/O2/O3 blocks, record shapes)
s = re.sub(r'<p class="eyebrow">(.*?)</p>', lambda m:f"\n_{txt(m.group(1))}_\n", s, flags=re.S)
s = re.sub(r'<h1>(.*?)</h1>', lambda m:f"\n# {flat(m.group(1))}\n", s, flags=re.S)
s = re.sub(r'<div class="sechead"><h2>(.*?)</h2><span class="tag">(.*?)</span></div>',
           lambda m:f"\n\n## {txt(m.group(1))}  ·  _{txt(m.group(2))}_\n", s, flags=re.S)
s = re.sub(r'<h2>(.*?)</h2>', lambda m:f"\n\n## {txt(m.group(1))}\n", s, flags=re.S)
s = re.sub(r'<div class="stnum">(.*?)</div>\s*<div class="sttitle">\s*<h3>(.*?)</h3>\s*<div class="stmeta">(.*?)</div>',
           lambda m:f"\n\n---\n\n### STEP {txt(m.group(1))} — {txt(m.group(2))}\n`{' | '.join(re.findall(r'<span[^>]*>(.*?)</span>', m.group(3)))}`\n", s, flags=re.S)
s = re.sub(r'<span class="pnum">(.*?)</span>\s*<div class="ptitle">\s*<h3>(.*?)</h3>',
           lambda m:f"\n\n---\n\n### PHASE {txt(m.group(1))} — {txt(m.group(2))}\n", s, flags=re.S)
# pivot: findings F1..F6 header  <span class="fid">F1</span><h3>…</h3><span class="pill …">…</span>
s = re.sub(r'<span class="fid">(.*?)</span>\s*<h3>(.*?)</h3>\s*<span class="pill[^"]*">(.*?)</span>',
           lambda m:f"\n\n### {txt(m.group(1))} — {txt(m.group(2))}  ·  _{txt(m.group(3))}_\n", s, flags=re.S)
# pivot: capability scope header  <span class="cnum">1</span><h3>…</h3><span class="st partial">partial</span><span class="owner">owner: X</span>
s = re.sub(r'<span class="cnum">(.*?)</span>\s*<h3>(.*?)</h3>\s*<span class="st[^"]*">(.*?)</span>\s*<span class="owner">(.*?)</span>',
           lambda m:f"\n\n### Capability {txt(m.group(1))} — {txt(m.group(2))}\n_state: {txt(m.group(3))} · {txt(m.group(4))}_\n", s, flags=re.S)
s = re.sub(r'<summary>(.*?)</summary>', lambda m:"\n**"+flat(m.group(1))+"**\n", s, flags=re.S)   # <details> folds
for h,f in (("h3","### {}"),("h4","**{}**"),("h5","**{}**")):
    s = re.sub(rf'<{h}[^>]*>(.*?)</{h}>', lambda m,f=f:"\n"+f.format(flat(m.group(1)))+"\n", s, flags=re.S)
s = re.sub(r'<span class="(?:lbl|xl|r|tagline)">(.*?)</span>', lambda m:f"\n> **{txt(m.group(1)).upper()}**\n", s, flags=re.S)
s = re.sub(r'<b>Verify</b>', '\n**Verify:**', s)
s = re.sub(r'<span class="gl">(.*?)</span>', lambda m:f"\n**{txt(m.group(1)).upper()}:** ", s, flags=re.S)
s = re.sub(r'<b>(If you drift here|Live defect · found in the tree|What to claim, and what not to)</b>',
           lambda m:f"\n**{txt(m.group(1))}**\n", s, flags=re.S)
# pivot: labelled blocks that were fusing with their body ("Done whenThe run loop…")
s = re.sub(r'<b>(Done when|Deferred if|Gate|Consequence|Recommendation|Action|Also missing)</b>\s*(?:<span>)?',
           lambda m:f"\n**{m.group(1)}:** ", s, flags=re.S)
# pivot: round steps  <span class="sn">Step 1</span><div class="sc"><b>Propose three</b>
s = re.sub(r'<span class="sn">(.*?)</span>\s*<div class="sc">\s*<b>(.*?)</b>',
           lambda m:f"\n**{txt(m.group(1))} — {txt(m.group(2))}**\n", s, flags=re.S)
# pivot: the seven-stage round strip
s = re.sub(r'<div class="rs[^"]*"><span class="n">(.*?)</span><span class="t">(.*?)</span><span class="sub">(.*?)</span><span class="cost">(.*?)</span></div>',
           lambda m:f"\n- **{txt(m.group(1))} {txt(m.group(2))}** — {txt(m.group(3))} · cost: {txt(m.group(4))}", s, flags=re.S)
# pivot: the autonomy ladder
s = re.sub(r'<div class="rung[^"]*"><span class="lvl">(.*?)</span><span class="desc">(.*?)</span>(?:<span class="mark">(.*?)</span>)?</div>',
           lambda m:f"\n- **{txt(m.group(1))}** — {txt(m.group(2))}" + (f"  ← **{txt(m.group(3)).upper()}**" if m.group(3) else ""), s, flags=re.S)
# pivot: test lists  <span class="tn">name</span><span class="td">what it asserts</span>
s = re.sub(r'<span class="tn">(.*?)</span>\s*<span class="td">(.*?)</span>',
           lambda m:f"`{txt(m.group(1))}` — {txt(m.group(2))}", s, flags=re.S)
# pivot: field labels inside record shapes / observables ("pattern", "O1")
s = re.sub(r'<span class="f">(.*?)</span>', lambda m:f"**{txt(m.group(1))}:** ", s, flags=re.S)
s = re.sub(r'<span class="sid">(.*?)</span><div class="sb"><b>(.*?)</b>',
           lambda m:f"\n**{txt(m.group(1))} — {txt(m.group(2))}**\n", s, flags=re.S)
s = re.sub(r'<span class="src (\w+)">[^<]*</span><span class="fx">(.*?)</span>',   # [^<]* not .*? — a bare src badge must not swallow the page
           lambda m:f"`[{m.group(1).upper()}]` {txt(m.group(2))}", s, flags=re.S)
s = re.sub(r'<span class="a (\w+)">.*?</span><span>(.*?)</span>',
           lambda m:f"**{m.group(1).upper()}** {txt(m.group(2))}", s, flags=re.S)
s = re.sub(r'<span class="k">(.*?)</span><span class="v[^"]*">(.*?)</span>',
           lambda m:f"- **{txt(m.group(1))}:** {txt(m.group(2))}", s, flags=re.S)
s = re.sub(r'<span class="chip[^"]*">(.*?)</span>', lambda m:f"[{txt(m.group(1))}] ", s, flags=re.S)
s = re.sub(r'<span class="won">(.*?)</span>', lambda m:f"**{txt(m.group(1))}** — ", s, flags=re.S)

def table(m):
    rows=[]
    for attrs, tr in re.findall(r'<tr([^>]*)>(.*?)</tr>', m.group(1), flags=re.S):   # was <tr> only → dropped every <tr class="fails">
        cells=[flat(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, flags=re.S)]
        if cells and 'fails' in attrs:
            cells[0] = '⚠ fails today · ' + cells[0]
        if cells: rows.append(cells)
    if not rows: return ''
    w=max(len(r) for r in rows); rows=[r+['']*(w-len(r)) for r in rows]
    o=['| '+' | '.join(rows[0])+' |','|'+'---|'*w]
    o+=['| '+' | '.join(c.replace('|','\\|') for c in r)+' |' for r in rows[1:]]
    return '\n'+'\n'.join(o)+'\n'
s = re.sub(r'<table[^>]*>(.*?)</table>', table, s, flags=re.S)
s = re.sub(r'<(?:li|dt|dd)[^>]*>(.*?)</(?:li|dt|dd)>', lambda m:f"- {flat(m.group(1))}", s, flags=re.S)
s = re.sub(r'<p[^>]*>(.*?)</p>', lambda m:f"\n{txt(m.group(1))}\n", s, flags=re.S)
s = re.sub(r'<figcaption>(.*?)</figcaption>', lambda m:f"\n_{txt(m.group(1))}_\n", s, flags=re.S)
s = re.sub(r'<[^>]+>','',s)                  # LAST tag strip …
s = html.unescape(s)                         # … then unescape, so `<=` survives
s = '\n'.join(re.sub(r'^\s+','',l).rstrip() for l in s.split('\n'))
s = re.sub(r'^- - ', '- ', s, flags=re.M)
s = re.sub(r'\n{3,}','\n\n',s)
for i,p in enumerate(pres):
    s = s.replace(f"\x00PRE{i}\x00", "\n```\n"+p+"\n```\n")

COMMON = """> Facts marked `[TREE]` were verified against `beating-nise` at commit `3e22b28` on 29 Aug 2026.
> Facts marked `[GIVEN]` are inherited from the task-space page — re-verify before relying on one.
> Reconciled against `~/Downloads/kuairand-starter-kit/` on 29 Aug (`Runbook_reconciliation.md`) and re-verified against the tree, the kit README and `baseline_scores.json` on 30 Aug: splits are **temporal, not by user**;
> `evaluate.py` is the sole scoring authority and must not be reimplemented; the submission key is
> `row_id` (not `sample_id`), and `(user_id, video_id)` is **not** unique; numpy-only is the kit's choice, not a rule.
> 30 Aug additions: the "Start, end, and the number" section, step 6 before 4 and 5, the oracle date filter, test_features for the submission run, 50/6 h marked [statement]."""
BANNERS = {
 "Execution_runbook.html": ("The L4-v Runbook",
  "> **Plain-text rendering of `Execution_runbook.html` (same directory), which is the authoritative source — the HTML carries the colour-coded status chips; the eight tests written to fail on the current tree are marked `⚠ fails today` in the test tables below.**\n>\n> Fourteen steps in dependency order. Companion to `Pivot_sequence.md`, which carries the architectural reasoning behind them."),
 "Pivot_sequence.html": ("The Pivot Sequence",
  "> **Plain-text rendering of `Pivot_sequence.html` (same directory), which is the authoritative source — the HTML carries eight SVG diagrams; each is reduced below to a `[diagram …]` line listing the diagram's own text labels.**\n>\n> Architecture direction, the refusals, one-owner-per-field arbitration over 13 papers, and ten capability scopes. Companion to `Execution_runbook.md`, which sequences these into runnable steps."),
}
title, intro = BANNERS.get(src.name, (src.stem, f"> Plain-text rendering of `{src.name}` (same directory), which is the authoritative source."))
head = f"<!--\n{title} — generated 29 Aug 2026 from {src.name}\nRegenerate: python3 tomd.py {src.name}\n-->\n\n{intro}\n>\n{COMMON}\n\n---\n\n"
dst.write_text(head + re.sub(r'\n{3,}','\n\n',s).strip()+"\n")
print(f"{src.name} -> {dst.name}  ({len(s):,} chars)")
