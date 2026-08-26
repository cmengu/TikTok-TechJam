"""Phase 7: research cache keyed by normalised query + protocol_hash."""

from __future__ import annotations


def get(query: str, protocol_hash: str):
    raise NotImplementedError


def put(query: str, protocol_hash: str, value) -> None:
    raise NotImplementedError
