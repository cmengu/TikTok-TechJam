"""Candidate-side progress/result/checkpoint writers (stdlib only).

Lives outside the harness package so the child never imports harness.*.
Copied into the workspace next to template.py by the runner.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _workspace() -> Path:
    raw = os.environ.get("WORKSPACE")
    if not raw:
        raise RuntimeError("WORKSPACE env var is required")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def progress(step: int, total: int, loss: float) -> None:
    ws = _workspace()
    line = {
        "step": int(step),
        "total": int(total),
        "loss": float(loss),
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with (ws / "progress.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\n")


def result(metrics: dict, preds_path: Path | str) -> None:
    ws = _workspace()
    payload = {
        "metrics": dict(metrics),
        "preds": str(preds_path),
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = ws / "result.json"
    tmp = ws / "result.json.tmp"
    tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


class checkpoint:
    @staticmethod
    def save(step: int, blob: bytes) -> Path:
        """Write already-serialized checkpoint bytes; keep last 3 by step."""
        ws = _workspace()
        ckpt_dir = ws / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        out = ckpt_dir / f"step-{int(step)}.pt"
        out.write_bytes(blob)
        files = sorted(
            ckpt_dir.glob("step-*.pt"),
            key=lambda p: int(p.stem.split("-", 1)[1]),
        )
        for old in files[:-3]:
            old.unlink(missing_ok=True)
        return out
