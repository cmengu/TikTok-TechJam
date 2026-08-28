"""Phase 7: research cache keyed by normalised query + protocol_hash."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

Outcome = Literal["confirmed", "contradicted"]


def _normalise(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def _key(query: str, protocol_hash: str) -> str:
    payload = _normalise(query) + "\0" + protocol_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResearchCache:
    """In-memory cache; optional events log for cache_lookup emissions."""

    def __init__(
        self,
        protocol_hash: str,
        *,
        events=None,
        node_id: int | None = None,
        path: Path | None = None,
    ) -> None:
        self.protocol_hash = protocol_hash
        self.events = events
        self.node_id = node_id
        self.path = path
        self._store: dict[str, dict[str, Any]] = {}
        if path and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._store[row["key"]] = row

    def get(self, query: str) -> tuple[bool, Outcome | None]:
        k = _key(query, self.protocol_hash)
        row = self._store.get(k)
        if row is None:
            if self.events is not None:
                self.events.emit(
                    "cache_lookup",
                    key=query,
                    hit=False,
                    summary=f"cache miss for {query}",
                )
            return False, None
        outcome = row.get("outcome")
        if self.events is not None:
            self.events.emit(
                "cache_lookup",
                key=query,
                hit=True,
                confirmed=outcome == "confirmed",
                contradicted=outcome == "contradicted",
                summary=f"cache hit {outcome} for {query}",
            )
        return True, outcome  # type: ignore[return-value]

    def put(self, query: str, outcome: Outcome) -> None:
        k = _key(query, self.protocol_hash)
        row = {"key": k, "query": query, "outcome": outcome}
        self._store[k] = row
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def get(cache: ResearchCache, query: str) -> tuple[bool, Outcome | None]:
    return cache.get(query)


def put(cache: ResearchCache, query: str, outcome: Outcome) -> None:
    cache.put(query, outcome)
