"""Phase 2: scripted schema-v1 event stream for the app."""

from __future__ import annotations

from pathlib import Path

SCRIPT: list[dict] = []


def write(run_dir: Path | str, speed: float = 20.0, instant: bool = False) -> str:
    """Emit SCRIPT through EventLog; return run id."""
    raise NotImplementedError
