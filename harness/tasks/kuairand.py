"""KuaiRand-Pure task adapter — wraps kit data splits and evaluate.py."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path
from typing import Literal

import numpy as np

from harness.kit import kit_module
from harness.protocol import Protocol
from harness.tasks.base import TaskPaths
from harness.tasks.synthetic import PLACEHOLDER_MAX, _is_placeholder, _sha256_file

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "kuairand"


def _score_script_sha() -> str:
    from harness.tasks import kuairand as mod

    return hashlib.sha256(inspect.getsource(mod.KuaiRandTask.score).encode("utf-8")).hexdigest()


class KuaiRandTask:
    name = "kuairand"
    metric = "primary"
    prediction_columns = ("row_id", "user_id", "video_id", "score")
    include_oracle_delta = True
    candidate_dir = REPO_ROOT / "candidate" / "kuairand"

    def __init__(self) -> None:
        self._paths: TaskPaths | None = None
        self._labels: dict[str, list[dict[str, str]]] = {}
        self._test_rows: list[tuple] | None = None

    def _data_dir(self) -> Path:
        if not DATA_DIR.is_dir():
            raise FileNotFoundError(
                f"KuaiRand data not built at {DATA_DIR}; "
                "run: python -m data.kuairand build --raw data/raw"
            )
        return DATA_DIR

    def _read_labels(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def prepare(self, protocol: Protocol, root: Path, *, seed: int = 0) -> TaskPaths:
        del root, seed
        data_dir = self._data_dir()
        harness_only = data_dir / "harness_only"
        raw = REPO_ROOT / "data" / "raw"
        if not raw.exists():
            from harness.kit import KIT_DIR

            raw = KIT_DIR / "KuaiRand-Pure" / "data"

        digests = {
            "train": _sha256_file(raw / "log_standard_4_08_to_4_21_pure.csv"),
            "test": _sha256_file(raw / "log_standard_4_22_to_5_08_pure.csv"),
            "search": _sha256_file(data_dir / "search_validation.csv"),
            "holdout": _sha256_file(data_dir / "oracle_features.csv"),
            "script": _score_script_sha(),
        }

        ruler = protocol.ruler
        expected = {
            "train": ruler["data"]["train"]["sha256"],
            "test": ruler["data"]["test"]["sha256"],
            "search": ruler["splits"]["search_validation"]["sha256"],
            "holdout": ruler["splits"]["holdout_validation"]["sha256"],
            "script": ruler["scoring"]["script_sha"],
        }
        for key, exp in expected.items():
            if _is_placeholder(str(exp)):
                continue
            if str(exp) != digests[key]:
                raise ValueError(
                    f"sha256 mismatch for {key}: yaml={exp} disk={digests[key]}"
                )

        evaluate_sha = ruler["scoring"].get("evaluate_sha")
        if evaluate_sha and not _is_placeholder(str(evaluate_sha)):
            from harness.kit import KIT_DIR

            actual = _sha256_file(KIT_DIR / "evaluate.py")
            if str(evaluate_sha) != actual:
                raise ValueError(f"evaluate_sha mismatch: yaml={evaluate_sha} disk={actual}")

        self._paths = TaskPaths(
            train=data_dir / "train.csv",
            search_validation=data_dir / "search_validation.csv",
            holdout_validation=data_dir / "oracle_features.csv",
            scoring_script=Path(__file__),
        )
        self._labels = {
            "search": self._read_labels(harness_only / "search_labels.csv"),
            "holdout": self._read_labels(harness_only / "oracle_labels.csv"),
        }
        kit_data = kit_module("data")
        raw = REPO_ROOT / "data" / "raw"
        if raw.exists():
            self._test_rows = kit_data.load(str(raw.resolve()))["test"]
        else:
            from harness.kit import KIT_DIR

            self._test_rows = kit_data.load(str(KIT_DIR / "KuaiRand-Pure" / "data"))["test"]

        (harness_only / "digests.json").write_text(
            json.dumps({**digests, "script": digests["script"]}, indent=2) + "\n",
            encoding="utf-8",
        )
        return self._paths

    def candidate_env(self, paths: TaskPaths, *, rung: str = "screen") -> dict[str, str]:
        env = {
            "TRAIN": str(paths.train),
            "VALID": str(paths.search_validation),
        }
        if rung == "holdout":
            env["ORACLE"] = str(paths.holdout_validation)
        return env

    def _labels_for(self, split: Literal["search", "holdout"]) -> list[dict[str, str]]:
        if split not in self._labels:
            raise RuntimeError("prepare() must be called before score()")
        return self._labels[split]

    @staticmethod
    def _read_preds(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise ValueError("empty prediction file")
            required = {"row_id", "user_id", "video_id", "score"}
            missing = required - set(reader.fieldnames)
            if missing:
                raise ValueError(f"preds missing columns: {sorted(missing)}")
            return list(reader)

    def score(
        self, preds_path: Path, split: Literal["search", "holdout"]
    ) -> dict[str, float]:
        if split == "test":  # type: ignore[comparison-overlap]
            raise KeyError("test labels are never scored by the harness")
        labels = self._labels_for(split)
        preds = self._read_preds(preds_path)
        n = len(labels)
        if len(preds) != n:
            raise ValueError(
                f"prediction count {len(preds)} != label count {n}"
            )
        row_ids = [int(p["row_id"]) for p in preds]
        if row_ids != list(range(n)):
            raise ValueError(
                f"row_id must be 0..{n - 1} contiguous; got {len(preds)} rows"
            )
        for i, (pred, lab) in enumerate(zip(preds, labels)):
            if pred["user_id"] != lab["user_id"] or pred["video_id"] != lab["video_id"]:
                raise ValueError(
                    f"row {i} alignment: pred ({pred['user_id']},{pred['video_id']}) "
                    f"!= label ({lab['user_id']},{lab['video_id']})"
                )
            score = float(pred["score"])
            if score != score or score in (float("inf"), float("-inf")):
                raise ValueError(f"row {i}: score is NaN/Inf")

        evaluate = kit_module("evaluate")
        users = [lab["user_id"] for lab in labels]
        y = [int(lab["long_view"]) for lab in labels]
        scores = [float(p["score"]) for p in preds]
        m = evaluate.evaluate(users, y, scores)
        return {
            "gauc": float(m["GAUC"]),
            "ndcg_at_5": float(m["nDCG@5"]),
            "primary": float(m["primary"]),
        }

    def rows(self, split: str) -> int:
        if split == "test":
            if self._test_rows is None:
                path = self._data_dir() / "harness_only" / "test_features.csv"
                with path.open(newline="", encoding="utf-8") as fh:
                    return sum(1 for _ in csv.DictReader(fh))
            return len(self._test_rows)
        mapping = {
            "train": "train.csv",
            "search": "search_validation.csv",
            "holdout": "oracle_features.csv",
        }
        if split not in mapping:
            raise KeyError(split)
        path = self._data_dir() / mapping[split]
        with path.open(newline="", encoding="utf-8") as fh:
            return sum(1 for _ in csv.DictReader(fh))

    def test_rows(self) -> list[tuple]:
        if self._test_rows is None:
            raise RuntimeError("prepare() must be called before test_rows()")
        return self._test_rows

    def submission_features(self) -> Path | None:
        return self._data_dir() / "harness_only" / "test_features.csv"

    def readback_submission(self, path: Path) -> dict:
        """Delegate to the kit's submit.read_submission contract."""
        submit = kit_module("submit")
        scores = submit.read_submission(str(path), self.test_rows())
        return {"ok": True, "rows": len(scores), "columns": list(submit.HEADER)}
