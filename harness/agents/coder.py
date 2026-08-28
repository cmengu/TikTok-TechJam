"""Phase 7: LLM coder that materialises a unified diff."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from harness.agents.contract import check_diff_contract, check_prompt_capability
from harness.agents.llm import log_usage
from harness.tree import Workspace
from harness.types import Hypothesis, Node

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "candidate" / "template.py"


class LLMCoder:
    def __init__(
        self,
        llm,
        workspace: Workspace,
        *,
        events=None,
        patches_dir: Path | None = None,
    ) -> None:
        self.llm = llm
        self.workspace = workspace
        self.events = events
        self.patches_dir = patches_dir or workspace.patches_dir

    def _template_source(self) -> str:
        src = self.workspace.path / "template.py"
        if src.is_file():
            return src.read_text(encoding="utf-8")
        return TEMPLATE_PATH.read_text(encoding="utf-8")

    def _build_prompt(
        self, hyp: Hypothesis, template_source: str, traceback: str | None
    ) -> str:
        parts = [
            "Write a unified diff for template.py implementing this hypothesis.",
            f"Stage/mechanism: {hyp.stage}/{hyp.mechanism}",
            f"Description: {hyp.description}",
            f"Citation: {hyp.citation}",
            "",
            "Template source:",
            template_source,
        ]
        if traceback:
            parts.extend(["", "Previous error:", traceback])
        return "\n".join(parts)

    def _try_apply(self, diff_path: Path) -> str | None:
        head = self.workspace.head()
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(diff_path)],
            cwd=str(self.workspace.path),
            capture_output=True,
            text=True,
        )
        err = None
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "git apply failed"
        self.workspace.checkout(head)
        return err

    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        del incumbent
        template_source = self._template_source()
        tb = traceback
        last_diff = ""

        for attempt in range(2):
            prompt = self._build_prompt(hyp, template_source, tb)
            prompt_errors = check_prompt_capability(prompt)
            if prompt_errors:
                tb = "; ".join(prompt_errors)
                if attempt == 0:
                    continue
                raise RuntimeError(tb)

            diff_text, usage = self.llm.complete("coder", prompt, None)
            if not isinstance(diff_text, str):
                diff_text = str(diff_text)
            last_diff = diff_text
            log_usage(self.events, hyp.parent_node or 0, "coding", usage)

            diff_errors = check_diff_contract(diff_text)
            if diff_errors:
                tb = "; ".join(diff_errors)
                if attempt == 0:
                    continue
                raise RuntimeError(tb)

            diff_path = self.patches_dir / f"{hyp.id}-{uuid.uuid4().hex[:8]}.diff"
            diff_path.write_text(diff_text, encoding="utf-8")

            apply_err = self._try_apply(diff_path)
            if apply_err:
                tb = apply_err
                if attempt == 0:
                    continue
                raise RuntimeError(apply_err)
            return diff_path

        raise RuntimeError(tb or "coder failed")
