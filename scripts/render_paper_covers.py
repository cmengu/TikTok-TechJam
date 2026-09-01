"""One-time cover builder for the Library card grid (fix-list item 1).

For every manifest entry whose url points at arXiv and whose pdf is still
null: download the PDF into papers/pdfs/, render page 1 to a PNG thumb in
papers/thumbs/ (both under the already-served /papers mount), and write the
relative paths back into papers/manifest.json (pdf, thumb). Entries without
a fetchable PDF (IEEE, GitHub) are left untouched — the Library renders them
as placeholder spines.

Run once from the repo root:  .venv/bin/python scripts/render_paper_covers.py
Safe to re-run: existing files are kept unless --force.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "papers"
MANIFEST = PAPERS / "manifest.json"
PDF_DIR = PAPERS / "pdfs"
THUMB_DIR = PAPERS / "thumbs"

THUMB_WIDTH = 480  # px; card covers render at ~240 CSS px, 2x for retina

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5})(v\d+)?")


def slug(entry: dict) -> str:
    m = ARXIV_RE.search(entry.get("url") or "")
    if m:
        return "arxiv-" + m.group("id").replace(".", "-")
    return re.sub(r"[^a-z0-9]+", "-", str(entry.get("title", "paper")).lower()).strip(
        "-"
    )[:60]


def arxiv_pdf_url(url: str) -> str | None:
    m = ARXIV_RE.search(url or "")
    if not m:
        return None
    return f"https://arxiv.org/pdf/{m.group('id')}"


def _ssl_context():
    # macOS pythons often lack the system CA bundle; certifi ships with pip.
    try:
        import certifi
        import ssl

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "luxmax-covers/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
        data = resp.read()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{url} did not return a PDF (got {data[:16]!r})")
    dest.write_bytes(data)


def render_thumb(pdf_path: Path, png_path: Path) -> None:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        page = doc[0]
        width = page.get_size()[0]
        image = page.render(scale=THUMB_WIDTH / width).to_pil()
        image.convert("RGB").save(png_path, format="PNG", optimize=True)
    finally:
        doc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download and re-render")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    PDF_DIR.mkdir(exist_ok=True)
    THUMB_DIR.mkdir(exist_ok=True)

    changed = False
    for entry in manifest:
        title = entry.get("title", "?")
        pdf_url = arxiv_pdf_url(entry.get("url") or "")
        existing_pdf = entry.get("pdf")
        if pdf_url is None and not existing_pdf:
            print(f"spine  {title[:60]} (no fetchable PDF)")
            continue

        name = slug(entry)
        pdf_path = (
            PAPERS / existing_pdf if existing_pdf else PDF_DIR / f"{name}.pdf"
        )
        png_path = THUMB_DIR / f"{name}.png"

        try:
            if not pdf_path.is_file() or args.force:
                assert pdf_url is not None
                print(f"fetch  {pdf_url} -> {pdf_path.relative_to(PAPERS)}")
                download(pdf_url, pdf_path)
            if not png_path.is_file() or args.force:
                render_thumb(pdf_path, png_path)
                print(f"thumb  {png_path.relative_to(PAPERS)}")
        except Exception as err:  # noqa: BLE001 — one bad paper must not sink the rest
            print(f"FAIL   {title[:60]}: {err}", file=sys.stderr)
            continue

        rel_pdf = str(pdf_path.relative_to(PAPERS))
        rel_thumb = str(png_path.relative_to(PAPERS))
        if entry.get("pdf") != rel_pdf or entry.get("thumb") != rel_thumb:
            entry["pdf"] = rel_pdf
            entry["thumb"] = rel_thumb
            changed = True

    if changed:
        MANIFEST.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"manifest updated: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
