"""Entrypoint for `python -m app`.

`python -m app.server` works too, via the __name__ guard in server.py; both
spellings land on the same serve().
"""

from __future__ import annotations

from app.server import serve

if __name__ == "__main__":
    serve()
