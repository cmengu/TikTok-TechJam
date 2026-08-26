"""Phase 8: training-only subsample (never touches eval rows)."""

from __future__ import annotations

from pathlib import Path


def training_subsample(
    parquet_root: Path | str,
    fraction: float,
    seed: int,
    keep_all_positives: bool = True,
    exclude_sample_ids=None,
) -> list[Path]:
    raise NotImplementedError
