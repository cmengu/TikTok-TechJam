"""Vercel entrypoint: the @vercel/python runtime looks for `app` here.

vercel.json rewrites every path (/, /static/*, /runs/*, /papers/*, ...)
to this function, so the FastAPI app behaves exactly as it does under
`python -m uvicorn app.server:app` — read-only over the committed runs/
records. Nothing here changes the local workflow.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.server import app  # noqa: E402,F401
