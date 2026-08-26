"""Phase 1: load protocols/*.yaml, canonical bytes, protocol_hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

_REQUIRED_KEYS = ("schema_version", "task", "ruler", "run")


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
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("protocol yaml must be a mapping")
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"missing required key: {key}")
    ruler = data["ruler"]
    if not isinstance(ruler, dict) or not ruler:
        raise ValueError("ruler must be a non-empty dict")
    return Protocol(
        task=data["task"],
        schema_version=data["schema_version"],
        ruler=ruler,
        run=data["run"],
        protocol_hash=protocol_hash(ruler),
        path=path,
    )


def _canonical_fragment(obj: object) -> str:
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return repr(float(obj))
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, dict):
        parts = []
        for key in sorted(obj.keys()):
            parts.append(
                f"{json.dumps(str(key), ensure_ascii=False)}:{_canonical_fragment(obj[key])}"
            )
        return "{" + ",".join(parts) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_canonical_fragment(v) for v in obj) + "]"
    raise TypeError(f"unsupported type for canonical_bytes: {type(obj)!r}")


def canonical_bytes(ruler: dict) -> bytes:
    """Sort keys recursively; floats via repr(float(x)); None -> null; utf-8."""
    if not isinstance(ruler, dict):
        raise TypeError("ruler must be a dict")
    return _canonical_fragment(ruler).encode("utf-8")


def protocol_hash(ruler: dict) -> str:
    """Return ``sha256:`` + hex of canonical_bytes; run block not included."""
    digest = hashlib.sha256(canonical_bytes(ruler)).hexdigest()
    return f"sha256:{digest}"
