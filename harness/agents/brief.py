"""Phase 7: deterministic brief composer from organisers' text + protocol."""

from __future__ import annotations

import hashlib
from pathlib import Path


def compose(organisers_text: Path, protocol) -> str:
    """Cut the organisers text at a stable boundary and append protocol summary."""
    raw = organisers_text.read_text(encoding="utf-8")
    marker = "## 0 · The one principle"
    if marker in raw:
        head = raw.split(marker, 1)[0].rstrip()
        rest = marker + raw.split(marker, 1)[1]
        section = rest.split("\n## 1 ·", 1)[0].rstrip()
        body = head + "\n\n" + section
    else:
        body = raw[:8000]
    task = getattr(protocol, "task", "unknown")
    phash = getattr(protocol, "protocol_hash", "")
    footer = (
        f"\n\n---\nprotocol.task={task}\n"
        f"protocol_hash={phash}\n"
        f"brief_sha256={hashlib.sha256(body.encode()).hexdigest()}\n"
    )
    return body + footer
