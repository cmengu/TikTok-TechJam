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

# Diff attempts before the full-file fallback: one fresh diff plus exactly one
# retry carrying the git error. Keeps the coder's cost bounded at 3 LLM calls.
DIFF_ATTEMPTS = 2

# Lines that can start a unified-diff header (outside hunk bodies).
_HEADER_PREFIXES = (
    "diff ",
    "index ",
    "--- ",
    "+++ ",
    "old mode",
    "new mode",
    "new file mode",
    "deleted file mode",
    "similarity index",
    "dissimilarity index",
    "rename from",
    "rename to",
    "copy from",
    "copy to",
    "Binary files",
)
# Lines that can appear inside a hunk body ("" covers blank context lines,
# which git apply tolerates and editors produce by stripping trailing spaces).
_BODY_PREFIXES = ("+", "-", " ", "\\")


def sanitize_diff(text: str) -> tuple[str, str | None]:
    """Keep only structurally-valid unified-diff lines; return (clean, error).

    Coder LLMs leak prose sentences around the diff body (seen on
    kuairand-20260901-004255: "recount: unexpected line: 'This imple…'").
    Prose outside hunk bodies — a preamble, text between files, or a trailing
    explanation — is stripped. Prose sandwiched *between* valid hunk-body
    lines is ambiguous (it could be a context line missing its prefix), so it
    fails cleanly here, BEFORE git apply, and the caller retries.
    """
    out: list[str] = []
    in_hunk = False
    # Invalid lines seen while inside a hunk; resolved when we learn whether
    # the hunk continued (error) or ended (trailing prose, safe to drop).
    pending: tuple[int, str] | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("@@") or line.startswith(_HEADER_PREFIXES):
            # A new hunk or header: anything invalid before it terminated the
            # previous hunk, exactly how --recount reads it. Drop the prose.
            pending = None
            in_hunk = line.startswith("@@")
            out.append(line)
            continue
        if in_hunk and (line == "" or line.startswith(_BODY_PREFIXES)):
            if pending is not None:
                return "", (
                    f"prose inside a diff hunk at line {pending[0]}: "
                    f"{pending[1][:80]!r} — resend a clean unified diff"
                )
            out.append(line)
            continue
        # Invalid line. Outside hunks it is prose — drop it. Inside a hunk,
        # hold it until we know whether the hunk continues.
        if in_hunk and pending is None and line.strip():
            pending = (lineno, line)
    clean = "\n".join(out)
    if not any(l.startswith("@@") for l in out):
        return "", "response contains no unified diff hunks"
    if not any(l.startswith("+++ ") or l.startswith("--- ") for l in out):
        return "", "response contains no unified diff file headers"
    return clean, None


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

    def _build_fullfile_prompt(
        self, hyp: Hypothesis, template_source: str, traceback: str | None
    ) -> str:
        parts = [
            "Previous unified diffs for this change failed to apply.",
            "Respond with the COMPLETE new content of template.py implementing "
            "this hypothesis — the whole file, valid Python, no diff markers, "
            "no prose, no fences.",
            f"Stage/mechanism: {hyp.stage}/{hyp.mechanism}",
            f"Description: {hyp.description}",
            f"Citation: {hyp.citation}",
            "",
            "Current template.py content:",
            template_source,
        ]
        if traceback:
            parts.extend(["", "Previous error:", traceback])
        return "\n".join(parts)

    def _emit_recovery(self, hyp: Hypothesis, attempt: int, action: str, detail: str) -> None:
        if self.events is None:
            return
        self.events.emit(
            "recovery",
            node=hyp.parent_node or 0,
            attempt=attempt,
            action=action,
            summary=f"coder {action} for {hyp.id}: {detail}"[:200],
            **{"class": "patch_apply_failed"},
        )

    def _try_apply(self, diff_path: Path) -> str | None:
        head = self.workspace.head()
        proc = subprocess.run(
            # --recount: LLM coders reliably miscount @@ hunk headers (seen on the
            # first full KuaiRand run — 3/3 patches rejected as "corrupt patch");
            # git re-derives the counts from the hunk body instead of trusting them.
            ["git", "apply", "--recount", "--whitespace=nowarn", str(diff_path)],
            cwd=str(self.workspace.path),
            capture_output=True,
            text=True,
        )
        err = None
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "git apply failed"
        self.workspace.checkout(head)
        return err

    def _write_diff(self, hyp: Hypothesis, diff_text: str, tag: str = "") -> Path:
        diff_path = self.patches_dir / f"{hyp.id}{tag}-{uuid.uuid4().hex[:8]}.diff"
        # git rejects a patch whose last line has no newline ("corrupt
        # patch at line N+1") — and the fence-stripper's strip() eats it.
        if not diff_text.endswith("\n"):
            diff_text += "\n"
        diff_path.write_text(diff_text, encoding="utf-8")
        return diff_path

    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        del incumbent
        template_source = self._template_source()
        tb = traceback

        for attempt in range(DIFF_ATTEMPTS):
            if attempt > 0:
                # The retry carries the exact git/sanitizer error plus the
                # current (unchanged — apply was rolled back) file content.
                self._emit_recovery(hyp, attempt, "patch_retried", tb or "")
            prompt = self._build_prompt(hyp, template_source, tb)
            prompt_errors = check_prompt_capability(prompt)
            if prompt_errors:
                tb = "; ".join(prompt_errors)
                if attempt == 0:
                    continue
                # The hypothesis text itself trips a capability rule; a
                # full-file prompt would embed the same text. Fail honestly.
                raise RuntimeError(tb)

            diff_text, usage = self.llm.complete("coder", prompt, None)
            if not isinstance(diff_text, str):
                diff_text = str(diff_text)
            log_usage(self.events, hyp.parent_node or 0, "coding", usage)

            diff_text, sanitize_err = sanitize_diff(diff_text)
            if sanitize_err:
                tb = sanitize_err
                continue

            diff_errors = check_diff_contract(diff_text)
            if diff_errors:
                tb = "; ".join(diff_errors)
                continue

            diff_path = self._write_diff(hyp, diff_text)
            apply_err = self._try_apply(diff_path)
            if apply_err is None:
                return diff_path
            tb = apply_err

        # Both diff attempts failed: fall back to full-file mode. Bounded to
        # the one file the coder ever edits (template.py) and one LLM call.
        self._emit_recovery(hyp, DIFF_ATTEMPTS, "fullfile_fallback", tb or "")
        return self._materialise_fullfile(hyp, template_source, tb)

    def _materialise_fullfile(
        self, hyp: Hypothesis, template_source: str, traceback: str | None
    ) -> Path:
        prompt = self._build_fullfile_prompt(hyp, template_source, traceback)
        prompt_errors = check_prompt_capability(prompt)
        if prompt_errors:
            raise RuntimeError("; ".join(prompt_errors))

        content, usage = self.llm.complete("coder", prompt, None)
        if not isinstance(content, str):
            content = str(content)
        log_usage(self.events, hyp.parent_node or 0, "coding", usage)
        if not content.endswith("\n"):
            content += "\n"

        try:
            compile(content, "template.py", "exec")
        except SyntaxError as exc:
            raise RuntimeError(
                f"full-file fallback returned invalid python: {exc}"
            ) from exc

        # Materialise as a real git diff so the node's provenance (patches/
        # dir, commit_node's re-apply, the diff contract) stays identical to
        # the cheap path.
        head = self.workspace.head()
        target = self.workspace.path / "template.py"
        target.write_text(content, encoding="utf-8")
        proc = subprocess.run(
            ["git", "diff", "--", "template.py"],
            cwd=str(self.workspace.path),
            capture_output=True,
            text=True,
        )
        self.workspace.checkout(head)
        if proc.returncode != 0:
            raise RuntimeError(
                f"git diff failed in full-file fallback: {proc.stderr.strip()}"
            )
        diff_text = proc.stdout
        if not diff_text.strip():
            raise RuntimeError(
                "full-file fallback returned the file unchanged — the "
                "hypothesis was not implemented"
            )

        diff_errors = check_diff_contract(diff_text)
        if diff_errors:
            raise RuntimeError("; ".join(diff_errors))

        diff_path = self._write_diff(hyp, diff_text, tag="-full")
        apply_err = self._try_apply(diff_path)
        if apply_err:
            raise RuntimeError(
                f"full-file fallback diff did not apply: {apply_err}"
            )
        return diff_path
