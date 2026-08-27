"""Phase 3: candidate-side progress/result/checkpoint writers (stdlib only)."""

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
    def save(state) -> Path:
        import torch  # local: report.py's module-level imports stay stdlib-only

        ws = _workspace()
        ckpt_dir = ws / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        step = int(state.get("step", 0)) if isinstance(state, dict) else 0
        if isinstance(state, dict) and "state_dict" in state:
            to_save = state["state_dict"]
            meta_step = step
        else:
            to_save = state
            meta_step = step
        out = ckpt_dir / f"step-{meta_step}.pt"
        torch.save(to_save, out)
        # keep last 3 by step number in filename
        files = sorted(
            ckpt_dir.glob("step-*.pt"),
            key=lambda p: int(p.stem.split("-", 1)[1]),
        )
        for old in files[:-3]:
            old.unlink(missing_ok=True)
        return out
