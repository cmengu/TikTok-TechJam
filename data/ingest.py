"""Phase 8: stream raw Ali-CCP CSV into partitioned parquet."""

from __future__ import annotations

from pathlib import Path


def parse_feature_string(s: str) -> dict[int, list[tuple[int, float]]]:
    raise NotImplementedError


def ingest(
    raw_dir: Path | str,
    out_dir: Path | str,
    n_buckets: int = 100,
    row_group: int = 200_000,
) -> str:
    raise NotImplementedError
