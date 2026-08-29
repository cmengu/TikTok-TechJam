"""KuaiRand-Pure ingest: wrap the kit's data.load(), emit harness CSV splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import yaml

from harness.kit import KIT_DIR, kit_module

LABEL = "long_view"
ORACLE_DATE_LO = 20220422
ORACLE_DATE_HI = 20220428
LABEL_COLUMNS = frozenset(
    {
        "is_click",
        "long_view",
        "is_like",
        "is_follow",
        "is_comment",
        "is_forward",
        "is_hate",
        "play_time_ms",
    }
)
FEATURE_COLUMNS = ("row_id", "date", "user_id", "video_id", "author_id", "tab", "duration_ms")
LABEL_FILE_COLUMNS = ("row_id", "user_id", "video_id", "long_view")

RAW_FILES = {
    "train": "log_standard_4_08_to_4_21_pure.csv",
    "test": "log_standard_4_22_to_5_08_pure.csv",
    "random_log": "log_random_4_22_to_5_08_pure.csv",
    "video_features": "video_features_basic_pure.csv",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_vid2author(raw_dir: Path) -> dict[str, str]:
    vid2author: dict[str, str] = {}
    path = raw_dir / RAW_FILES["video_features"]
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            vid2author[row["video_id"]] = row["author_id"]
    return vid2author


def _row_tuple(date: int, user_id: str, video_id: str, author_id: str, tab: str, duration_ms: float, label: int):
    return (date, user_id, video_id, author_id, tab, duration_ms, label)


def _write_features(path: Path, rows: list[tuple], *, with_label: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(FEATURE_COLUMNS)
    if with_label:
        cols.append(LABEL)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row_id, row in enumerate(rows):
            record = {
                "row_id": row_id,
                "date": row[0],
                "user_id": row[1],
                "video_id": row[2],
                "author_id": row[3],
                "tab": row[4],
                "duration_ms": row[5],
            }
            if with_label:
                record[LABEL] = row[6]
            writer.writerow(record)


def _write_labels(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LABEL_FILE_COLUMNS)
        writer.writeheader()
        for row_id, row in enumerate(rows):
            writer.writerow(
                {
                    "row_id": row_id,
                    "user_id": row[1],
                    "video_id": row[2],
                    "long_view": row[6],
                }
            )


def _read_oracle_rows(raw_dir: Path) -> list[tuple]:
    vid2author = _load_vid2author(raw_dir)
    rows: list[tuple] = []
    path = raw_dir / RAW_FILES["random_log"]
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            date = int(raw["date"])
            if not (ORACLE_DATE_LO <= date <= ORACLE_DATE_HI):
                continue
            label = 1 if raw[LABEL] != "0" else 0
            rows.append(
                _row_tuple(
                    date,
                    raw["user_id"],
                    raw["video_id"],
                    vid2author.get(raw["video_id"], "UNK"),
                    raw["tab"],
                    float(raw["duration_ms"]),
                    label,
                )
            )
    return rows


def _composition(rows: list[tuple]) -> dict[str, float | int]:
    by_user: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_user[row[1]].append(row[6])
    users = len(by_user)
    no_pos = all_pos = 0
    for labels in by_user.values():
        s = sum(labels)
        if s == 0:
            no_pos += 1
        elif s == len(labels):
            all_pos += 1
    return {
        "users": users,
        "no_positive_pct": round(100.0 * no_pos / users, 1) if users else 0.0,
        "all_positive_pct": round(100.0 * all_pos / users, 1) if users else 0.0,
        "no_pair_pct": round(100.0 * (no_pos + all_pos) / users, 1) if users else 0.0,
    }


def build(raw_dir: Path, out_dir: Path, protocol_path: Path) -> dict[str, str]:
    """Write split CSVs and refresh digest fields in the protocol yaml."""
    kit_data = kit_module("data")
    splits = kit_data.load(str(raw_dir))

    train_rows = splits["train"]
    valid_rows = splits["valid"]
    test_rows = splits["test"]
    oracle_rows = _read_oracle_rows(raw_dir)

    _write_features(out_dir / "train.csv", train_rows, with_label=True)
    _write_features(out_dir / "search_validation.csv", valid_rows, with_label=False)
    _write_features(out_dir / "oracle_features.csv", oracle_rows, with_label=False)
    _write_labels(out_dir / "harness_only" / "search_labels.csv", valid_rows)
    _write_labels(out_dir / "harness_only" / "oracle_labels.csv", oracle_rows)
    _write_features(out_dir / "harness_only" / "test_features.csv", test_rows, with_label=False)

    digests = {
        "data_train": sha256_file(raw_dir / RAW_FILES["train"]),
        "data_test": sha256_file(raw_dir / RAW_FILES["test"]),
        "data_random_log": sha256_file(raw_dir / RAW_FILES["random_log"]),
        "data_video_features": sha256_file(raw_dir / RAW_FILES["video_features"]),
        "split_train": sha256_file(out_dir / "train.csv"),
        "split_search": sha256_file(out_dir / "search_validation.csv"),
        "split_holdout": sha256_file(out_dir / "oracle_features.csv"),
        "split_test": sha256_file(out_dir / "harness_only" / "test_features.csv"),
        "labels_search": sha256_file(out_dir / "harness_only" / "search_labels.csv"),
        "labels_holdout": sha256_file(out_dir / "harness_only" / "oracle_labels.csv"),
        "evaluate": sha256_file(KIT_DIR / "evaluate.py"),
        "submit": sha256_file(KIT_DIR / "submit.py"),
    }

    (out_dir / "harness_only" / "digests.json").write_text(
        json.dumps(digests, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    proto = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    ruler = proto["ruler"]
    ruler["data"]["train"]["sha256"] = digests["data_train"]
    ruler["data"]["test"]["sha256"] = digests["data_test"]
    ruler["data"]["random_log"]["sha256"] = digests["data_random_log"]
    ruler["data"]["random_log"]["rows"] = sum(
        1
        for _ in open(raw_dir / RAW_FILES["random_log"], encoding="utf-8")
    ) - 1
    ruler["data"]["video_features"]["sha256"] = digests["data_video_features"]
    ruler["splits"]["train"]["sha256"] = digests["split_train"]
    ruler["splits"]["train"]["rows"] = len(train_rows)
    ruler["splits"]["search_validation"]["sha256"] = digests["split_search"]
    ruler["splits"]["search_validation"]["rows"] = len(valid_rows)
    ruler["splits"]["holdout_validation"]["sha256"] = digests["split_holdout"]
    ruler["splits"]["holdout_validation"]["rows"] = len(oracle_rows)
    ruler["splits"]["test"]["rows"] = len(test_rows)
    ruler["scoring"]["evaluate_sha"] = digests["evaluate"]
    ruler["scoring"]["submit_sha"] = digests["submit"]
    ruler["composition"]["valid"] = _composition(valid_rows)
    protocol_path.write_text(yaml.safe_dump(proto, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return digests


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KuaiRand harness CSV splits.")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--raw", type=Path, required=True, help="Raw KuaiRand-Pure/data directory")
    parser.add_argument("--out", type=Path, default=Path("data/kuairand"))
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/kuairand.yaml"),
        help="Protocol yaml to update with digests",
    )
    args = parser.parse_args()
    if args.command == "build":
        digests = build(args.raw.resolve(), args.out.resolve(), args.protocol.resolve())
        print(f"Wrote splits to {args.out}")
        print(f"Updated {args.protocol}")
        print(f"oracle rows (0422-0428): {digests['split_holdout'][:12]}…")


if __name__ == "__main__":
    main()
