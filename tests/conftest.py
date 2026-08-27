"""Shared fixtures for harness tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import placeholder_protocol


@pytest.fixture
def placeholder_proto(tmp_path: Path):
    return placeholder_protocol(tmp_path)
