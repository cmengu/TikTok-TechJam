"""Phase 1: load protocols/*.yaml, canonical bytes, protocol_hash."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Protocol:
    task: str
    schema_version: int
    ruler: dict
    run: dict
    protocol_hash: str
    path: Path


def load(path: Path | str) -> Protocol:
    """Validate required keys; nulls allowed under ruler."""
    raise NotImplementedError


def canonical_bytes(ruler: dict) -> bytes:
    """Sort keys recursively; floats via repr(float(x)); None -> null; utf-8."""
    raise NotImplementedError


def protocol_hash(ruler: dict) -> str:
    """Return ``sha256:`` + hex of canonical_bytes; run block not included."""
    raise NotImplementedError
