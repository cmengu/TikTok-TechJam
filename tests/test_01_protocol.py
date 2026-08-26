"""Phase 1: protocol load, canonical bytes, protocol_hash."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness import protocol as proto

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "protocols" / "synthetic.yaml"
ALICCP = ROOT / "protocols" / "aliccp.yaml"


def _ruler() -> dict:
    return yaml.safe_load(SYNTHETIC.read_text())["ruler"]


def test_reorder_same_hash():
    ruler = _ruler()
    keys = list(ruler.keys())
    reordered = {k: ruler[k] for k in reversed(keys)}
    assert list(reordered.keys()) != list(ruler.keys())
    assert proto.protocol_hash(ruler) == proto.protocol_hash(reordered)


def test_float_formatting_same_hash():
    base = {"epsilon": 0.1, "n": 1}
    variants = [
        {"epsilon": 0.10, "n": 1},
        {"epsilon": 0.1, "n": 1},
        {"epsilon": 1e-1, "n": 1},
    ]
    hashes = {proto.protocol_hash(base)}
    for v in variants:
        hashes.add(proto.protocol_hash(v))
    assert len(hashes) == 1


def test_comment_same_hash(tmp_path: Path):
    text = SYNTHETIC.read_text()
    h1 = proto.load(SYNTHETIC).protocol_hash
    commented = text.replace("\nruler:", "\n# phase-1 comment probe\nruler:", 1)
    assert "# phase-1 comment probe" in commented
    path = tmp_path / "synthetic_commented.yaml"
    path.write_text(commented)
    h2 = proto.load(path).protocol_hash
    assert h1 == h2


def test_ruler_change_new_hash():
    ruler = _ruler()
    changed = yaml.safe_load(yaml.dump(ruler))
    changed["metrics"]["cvr_auc"]["population"] = "all_impressions"
    assert changed["metrics"]["cvr_auc"]["population"] != ruler["metrics"]["cvr_auc"]["population"]
    assert proto.protocol_hash(ruler) != proto.protocol_hash(changed)


def test_run_block_not_hashed(tmp_path: Path):
    data = yaml.safe_load(SYNTHETIC.read_text())
    h1 = proto.protocol_hash(data["ruler"])
    data["run"]["budget"]["gpu_hours"] = 999.0
    path = tmp_path / "budget_changed.yaml"
    path.write_text(yaml.dump(data))
    loaded = proto.load(path)
    assert loaded.protocol_hash == h1
    assert loaded.run["budget"]["gpu_hours"] == 999.0


def test_missing_ruler_raises(tmp_path: Path):
    data = yaml.safe_load(SYNTHETIC.read_text())
    del data["ruler"]
    path = tmp_path / "no_ruler.yaml"
    path.write_text(yaml.dump(data))
    with pytest.raises(ValueError, match="ruler"):
        proto.load(path)


def test_nulls_allowed():
    p = proto.load(ALICCP)
    assert p.task == "aliccp"
    assert p.ruler["convergence"]["epsilon"] is None
    assert p.protocol_hash.startswith("sha256:")
    assert len(p.protocol_hash) == len("sha256:") + 64
