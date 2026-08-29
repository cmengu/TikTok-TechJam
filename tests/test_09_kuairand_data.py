"""KuaiRand-Pure data layer tests (step 2)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
import yaml

from harness.kit import KIT_DIR, kit_module
from harness.protocol import load as load_protocol
from data.kuairand import LABEL, LABEL_COLUMNS, ORACLE_DATE_HI, ORACLE_DATE_LO, sha256_file

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "kuairand"
PROTOCOL_PATH = ROOT / "protocols" / "kuairand.yaml"
RAW_LINK = ROOT / "data" / "raw"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT / "train.csv").exists(),
    reason="KuaiRand splits not built; run: python -m data.kuairand build --raw data/raw",
)


def _protocol() -> dict:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_digests_match_protocol():
    proto = _protocol()
    ruler = proto["ruler"]
    file_checks = {
        DATA_ROOT / "train.csv": ruler["splits"]["train"]["sha256"],
        DATA_ROOT / "search_validation.csv": ruler["splits"]["search_validation"]["sha256"],
        DATA_ROOT / "oracle_features.csv": ruler["splits"]["holdout_validation"]["sha256"],
        KIT_DIR / "evaluate.py": ruler["scoring"]["evaluate_sha"],
        KIT_DIR / "submit.py": ruler["scoring"]["submit_sha"],
    }
    for path, expected in file_checks.items():
        assert sha256_file(path) == expected, path.name
    if RAW_LINK.exists():
        raw = RAW_LINK.resolve()
        assert sha256_file(raw / "log_standard_4_08_to_4_21_pure.csv") == ruler["data"]["train"]["sha256"]
        assert sha256_file(raw / "log_standard_4_22_to_5_08_pure.csv") == ruler["data"]["test"]["sha256"]
        assert sha256_file(raw / "log_random_4_22_to_5_08_pure.csv") == ruler["data"]["random_log"]["sha256"]
        assert sha256_file(raw / "video_features_basic_pure.csv") == ruler["data"]["video_features"]["sha256"]


def test_no_placeholder_digests():
    proto = _protocol()
    ruler = proto["ruler"]
    paths = [
        ruler["data"]["train"]["sha256"],
        ruler["data"]["test"]["sha256"],
        ruler["data"]["random_log"]["sha256"],
        ruler["data"]["video_features"]["sha256"],
        ruler["splits"]["train"]["sha256"],
        ruler["splits"]["search_validation"]["sha256"],
        ruler["splits"]["holdout_validation"]["sha256"],
        ruler["scoring"]["evaluate_sha"],
        ruler["scoring"]["submit_sha"],
    ]
    for value in paths:
        assert value != "pending"
        assert len(value) == 64
        assert int(value, 16) > 15


def test_oracle_features_have_no_label():
    rows = _read_csv(DATA_ROOT / "oracle_features.csv")
    assert rows
    forbidden = LABEL_COLUMNS | {LABEL, "label", "target"}
    for col in rows[0]:
        assert col.lower() not in forbidden
        assert not col.lower().endswith("_label")


def test_splits_are_the_kits():
    kit_data = kit_module("data")
    raw_dir = str(RAW_LINK.resolve()) if RAW_LINK.exists() else str(
        KIT_DIR / "KuaiRand-Pure" / "data"
    )
    splits = kit_data.load(raw_dir)

    train_rows = _read_csv(DATA_ROOT / "train.csv")
    valid_rows = _read_csv(DATA_ROOT / "search_validation.csv")
    assert len(train_rows) == len(splits["train"])
    assert len(valid_rows) == len(splits["valid"])

    for idx, (file_row, kit_row) in enumerate(zip(train_rows, splits["train"])):
        assert int(file_row["row_id"]) == idx
        assert int(file_row["date"]) == kit_row[0]
        assert file_row["user_id"] == kit_row[1]
        assert file_row["video_id"] == kit_row[2]
        assert int(file_row["long_view"]) == kit_row[6]

    for idx, (file_row, kit_row) in enumerate(zip(valid_rows, splits["valid"])):
        assert int(file_row["row_id"]) == idx
        assert int(file_row["date"]) == kit_row[0]
        assert ORACLE_DATE_LO <= int(file_row["date"]) <= ORACLE_DATE_HI


def test_no_test_dated_row_is_candidate_visible():
    test_date = re.compile(r"202204(29|30)|2022050[0-8]")
    label_free = [DATA_ROOT / "search_validation.csv", DATA_ROOT / "oracle_features.csv"]
    for path in label_free:
        rows = _read_csv(path)
        for row in rows:
            assert not test_date.search(str(row["date"])), path.name
        assert LABEL not in rows[0]
    test_rows = _read_csv(DATA_ROOT / "harness_only" / "test_features.csv")
    assert test_rows
    assert LABEL not in test_rows[0]
    for row in test_rows:
        assert int(row["date"]) >= 20220429


def test_composition_matches_protocol():
    proto = _protocol()
    labels = _read_csv(DATA_ROOT / "harness_only" / "search_labels.csv")
    by_user: dict[str, list[int]] = {}
    for row in labels:
        by_user.setdefault(row["user_id"], []).append(int(row["long_view"]))
    users = len(by_user)
    no_pos = sum(1 for vals in by_user.values() if sum(vals) == 0)
    all_pos = sum(1 for vals in by_user.values() if sum(vals) == len(vals))
    recorded = proto["ruler"]["composition"]["valid"]
    assert recorded["users"] == users
    assert recorded["no_positive_pct"] == round(100.0 * no_pos / users, 1)
    assert recorded["all_positive_pct"] == round(100.0 * all_pos / users, 1)
    assert recorded["no_pair_pct"] == round(100.0 * (no_pos + all_pos) / users, 1)
    test_comp = proto["ruler"]["composition"]["test"]
    assert test_comp["no_positive_pct"] == 27.1
    assert test_comp["all_positive_pct"] == 9.2


def test_protocol_loads():
    proto = load_protocol(PROTOCOL_PATH)
    assert proto.task == "kuairand"
