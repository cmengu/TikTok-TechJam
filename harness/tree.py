"""Phase 6: run tree, hypothesis queue, workspace, ladder loop."""

from __future__ import annotations

import json
import re
import shutil
import statistics
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from harness.events import EventLog
from harness.measure import METRIC, SeedCache
from harness.types import Cost, Hypothesis, Node, RunResult, Verdict

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = REPO_ROOT / "candidate"

TRANSITIONS: dict[str, set[str]] = {
    "screening": {"running", "retired"},
    "running": {
        "replicating",
        "inconclusive",
        "rejected",
        "debugging",
        "leaked",
        "retired",
    },
    "replicating": {"promoted", "inconclusive", "rejected", "leaked", "retired"},
    "debugging": {"running", "retired"},
    "inconclusive": {"replicating", "retired"},
    "promoted": {"retired"},
    "rejected": set(),
    "leaked": set(),
    "retired": set(),
}
STALL_STEPS = 4
MAX_LIVE_BRANCHES = 3
DEBUG_DEPTH = 3
LESSONS_WINDOW = 30

# Locked: Phase-5 calibrate / SeedCache / scorecard keys (not #p6's stale 0,1,2).
SCREEN_SEED = 1
FULL_SEEDS = (1, 2, 3)
SCREEN_SEEDS_CAL = (1, 2, 3, 4, 5)
HOLDOUT_SEEDS = (0, 1, 2)
SMOKE_TIMEOUT_S = 60.0
ATTRIBUTION_HAND = "clear"


class IllegalTransition(Exception):
    """Raised when a node state change is not in TRANSITIONS."""


def transition(node: Node, new_state: str) -> None:
    allowed = TRANSITIONS.get(node.state, set())
    if new_state not in allowed:
        raise IllegalTransition(f"{node.state!r} → {new_state!r}")
    node.state = new_state  # type: ignore[assignment]


class Coder(Protocol):
    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        ...


class PatchCoder:
    def materialise(
        self, hyp: Hypothesis, incumbent: Node, traceback: str | None
    ) -> Path:
        del incumbent, traceback
        if hyp.patch is None:
            raise ValueError(f"hypothesis {hyp.id} has no patch")
        return Path(hyp.patch)


class Workspace:
    """Git repo at runs/<id>/workspace; branch run/<id>; initial commit = template."""

    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.path = self.run_dir / "workspace"
        self.patches_dir = self.run_dir / "patches"
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        self.path.mkdir(parents=True, exist_ok=True)
        if not (self.path / ".git").exists():
            self._init_repo()

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            check=check,
            capture_output=True,
            text=True,
        )

    def _init_repo(self) -> None:
        for name in ("template.py", "report.py"):
            shutil.copy2(CANDIDATE_DIR / name, self.path / name)
        self._git("init")
        self._git("checkout", "-b", f"run/{self.run_id}")
        self._git("config", "user.email", "harness@local")
        self._git("config", "user.name", "harness")
        self._git("add", "template.py", "report.py")
        self._git("commit", "-m", "initial")

    def head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def commit_node(self, node_id: int, diff_path: Path) -> str:
        diff_path = Path(diff_path)
        if diff_path.is_file() and diff_path.stat().st_size > 0:
            applied = self._git("apply", "--whitespace=nowarn", str(diff_path), check=False)
            if applied.returncode != 0:
                raise RuntimeError(
                    f"git apply failed for node {node_id}: {applied.stderr}"
                )
        self._git("add", "-A")
        msg = f"node {node_id:03d}"
        # Allow empty commit when patch is a no-op (base hyp).
        self._git("commit", "--allow-empty", "-m", msg)
        sha = self.head()
        patch_out = self.patches_dir / f"node-{node_id:03d}.diff"
        parent = self._git("rev-parse", "HEAD~1").stdout.strip()
        diff = self._git("diff", f"{parent}..HEAD")
        patch_out.write_text(diff.stdout, encoding="utf-8")
        return sha

    def checkout(self, commit: str) -> None:
        self._git("checkout", "--force", commit)


class Queue:
    def __init__(self, events: EventLog) -> None:
        self.events = events
        self._items: list[Hypothesis] = []
        self._seen: set[tuple[str, str, str]] = set()

    @staticmethod
    def _norm(description: str) -> str:
        return re.sub(r"\s+", " ", description.strip().lower())

    @staticmethod
    def _key(hyp: Hypothesis) -> tuple[str, str, str]:
        return (hyp.stage, hyp.mechanism, Queue._norm(hyp.description))

    def push(self, hyp: Hypothesis) -> bool:
        key = self._key(hyp)
        if key in self._seen:
            self.events.emit(
                "rule_trip",
                rule="duplicate",
                id=hyp.id,
                summary=f"duplicate hypothesis {hyp.id}",
            )
            return False
        self._seen.add(key)
        self._items.append(hyp)
        self.events.emit(
            "hypothesis_queued",
            id=hyp.id,
            stage=hyp.stage,
            mechanism=hyp.mechanism,
            description=hyp.description,
            expected_gain=hyp.expected_gain,
            expected_gpu_h=hyp.expected_gpu_h,
            parent_node=hyp.parent_node,
            summary=f"queued {hyp.id} ({hyp.stage}/{hyp.mechanism})",
        )
        return True

    def __len__(self) -> int:
        return len(self._items)

    def peek_ids(self) -> list[str]:
        return [h.id for h in self._items]

    def score_hyp(self, hyp: Hypothesis, stats: dict[str, dict]) -> float:
        fam = f"{hyp.stage}/{hyp.mechanism}"
        row = stats.get(fam)
        if row and row.get("n", 0) > 0:
            mean_d = float(row["mean_delta"])
            sd = float(row["sd_delta"])
            gpu = max(float(row["mean_gpu_min"]), 1e-9)
            return (mean_d + sd) / gpu
        # Cold-start: expected_gain / expected_gpu_h (hours → minutes-ish scale).
        gpu_h = max(float(hyp.expected_gpu_h), 1e-9)
        return float(hyp.expected_gain) / (gpu_h * 60.0)

    def rerank(self, stats: dict[str, dict]) -> list[str]:
        self._items.sort(
            key=lambda h: (-self.score_hyp(h, stats), -h.expected_gain, h.id)
        )
        order = [h.id for h in self._items]
        self.events.emit(
            "queue_reordered",
            order=order,
            summary=f"queue reranked ({len(order)} items)",
        )
        return order

    def pop(self) -> Hypothesis:
        if not self._items:
            raise IndexError("queue empty")
        return self._items.pop(0)


def family_stats(events: list[dict]) -> dict[str, dict]:
    """Pure fold: per-family mean Δ, sd, n, mean gpu_min from the event log."""
    hyp_family: dict[str, str] = {}
    node_family: dict[int, str] = {}
    for ev in events:
        typ = ev.get("type")
        if typ == "hypothesis_queued":
            hid = ev.get("id")
            if hid is not None:
                hyp_family[str(hid)] = f"{ev.get('stage')}/{ev.get('mechanism')}"
        elif typ == "node_created":
            nid = ev.get("id")
            hid = ev.get("hypothesis_id")
            if nid is not None and hid is not None and str(hid) in hyp_family:
                node_family[int(nid)] = hyp_family[str(hid)]

    buckets: dict[str, dict[str, list[float]]] = {}
    for ev in events:
        if ev.get("type") != "verdict":
            continue
        nid = ev.get("node")
        if nid is None:
            continue
        fam = node_family.get(int(nid))
        if fam is None:
            continue
        delta = ev.get("delta_mean")
        if delta is None:
            continue
        gpu = float(ev.get("gpu_min", 1.0))
        bucket = buckets.setdefault(fam, {"deltas": [], "gpu": []})
        bucket["deltas"].append(float(delta))
        bucket["gpu"].append(gpu)

    out: dict[str, dict] = {}
    for fam, b in buckets.items():
        deltas = b["deltas"]
        gpus = b["gpu"]
        n = len(deltas)
        mean_d = statistics.mean(deltas) if deltas else 0.0
        sd = statistics.stdev(deltas) if n >= 2 else 0.0
        out[fam] = {
            "mean_delta": mean_d,
            "sd_delta": sd,
            "n": n,
            "mean_gpu_min": statistics.mean(gpus) if gpus else 1.0,
        }
    return out


@dataclass
class RebuildState:
    nodes: dict[int, dict[str, Any]]
    queue_order: list[str]
    incumbent_id: int | None
    hyp_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)


def rebuild(events: list[dict]) -> RebuildState:
    """Pure fold over events.jsonl → nodes / queue order / incumbent."""
    nodes: dict[int, dict[str, Any]] = {}
    queue_order: list[str] = []
    hyp_by_id: dict[str, dict[str, Any]] = {}
    incumbent_id: int | None = None
    started: set[str] = set()

    for ev in events:
        typ = ev.get("type")
        if typ == "hypothesis_queued":
            hid = str(ev["id"])
            hyp_by_id[hid] = dict(ev)
            if hid not in queue_order and hid not in started:
                queue_order.append(hid)
        elif typ == "queue_reordered":
            order = [str(x) for x in (ev.get("order") or [])]
            named = set(order)
            rest = [h for h in queue_order if h not in named]
            queue_order = [h for h in order if h in hyp_by_id or h in queue_order] + rest
        elif typ == "node_created":
            nid = int(ev["id"])
            hid = ev.get("hypothesis_id")
            nodes[nid] = {
                "id": nid,
                "parent": ev.get("parent"),
                "kind": ev.get("kind"),
                "hypothesis_id": hid,
                "state": "screening",
                "commit": None,
            }
            if hid is not None:
                started.add(str(hid))
                queue_order = [h for h in queue_order if h != str(hid)]
        elif typ in ("state_changed", "verdict"):
            nid = ev.get("node")
            state = ev.get("state")
            if nid is not None and state is not None and int(nid) in nodes:
                nodes[int(nid)]["state"] = state
        elif typ == "incumbent_changed":
            nid = ev.get("node")
            if nid is not None:
                incumbent_id = int(nid)
        elif typ == "run_ended":
            if ev.get("incumbent") is not None:
                incumbent_id = int(ev["incumbent"])

    return RebuildState(
        nodes=nodes,
        queue_order=queue_order,
        incumbent_id=incumbent_id,
        hyp_by_id=hyp_by_id,
    )


# Back-compat name used in the lock / tests.
TreeRebuild = rebuild


class Tree:
    def __init__(
        self,
        events: EventLog,
        protocol,
        task,
        runner,
        measure,
        coder,
        queue: Queue,
        max_nodes: int,
        budget,
        workspace: Workspace | None = None,
        hyp_index: dict[str, Hypothesis] | None = None,
        screen_timeout_s: float = 300.0,
        full_timeout_s: float = 600.0,
        smoke_timeout_s: float = SMOKE_TIMEOUT_S,
        attribution: str = ATTRIBUTION_HAND,
    ) -> None:
        self.events = events
        self.protocol = protocol
        self.task = task
        self.runner = runner
        self.measure = measure
        self.coder = coder
        self.queue = queue
        self.max_nodes = int(max_nodes)
        self.budget = budget
        self.workspace = workspace
        self.hyp_index = dict(hyp_index or {})
        self.screen_timeout_s = float(screen_timeout_s)
        self.full_timeout_s = float(full_timeout_s)
        self.smoke_timeout_s = float(smoke_timeout_s)
        self.attribution = attribution
        self._initial_commit = workspace.head() if workspace is not None else None

        self.nodes: dict[int, Node] = {}
        self.incumbent: Node | None = None
        self.screen_inc = SeedCache({})
        self.full_inc = SeedCache({})
        self.holdout_inc = SeedCache({})
        self._nodes_done = 0
        self._stall = 0
        self._promotions = 0
        self._holdout_done_first = False
        self._best_reported = 0.0
        self._debug_depth: dict[int, int] = {}  # node_id → depth along debug lineage
        self._preallocated: dict[str, int] = {}
        self._lessons_path = Path(events._run_dir) / "lessons.jsonl"  # noqa: SLF001
        self._gpu_spent_s = 0.0
        self._ended = False

        # Point runner at the git workspace working tree when present.
        if self.workspace is not None:
            self.runner.run_cfg["candidate_src"] = str(self.workspace.path)

    @staticmethod
    def rebuild(events: list[dict]) -> RebuildState:
        return rebuild(events)

    def _read_log(self) -> list[dict]:
        path = Path(self.events._run_dir) / "events.jsonl"  # noqa: SLF001
        if not path.is_file():
            return []
        # Ensure writer has flushed pending lines.
        try:
            self.events._events_file.flush()  # noqa: SLF001
        except Exception:
            pass
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def _live_count(self) -> int:
        return sum(
            1
            for n in self.nodes.values()
            if n.state in ("running", "replicating")
        )

    def _set_state(self, node: Node, new_state: str, summary: str | None = None) -> None:
        transition(node, new_state)
        self.events.emit(
            "state_changed",
            node=node.id,
            state=new_state,
            summary=summary or f"node {node.id} → {new_state}",
        )

    def _append_lesson(
        self,
        node: Node,
        family: str,
        delta: float | None,
        gpu_min: float,
        diff_summary: str,
    ) -> None:
        row = {
            "node": node.id,
            "family": family,
            "delta": delta,
            "gpu_min": gpu_min,
            "diff_summary": diff_summary,
        }
        with self._lessons_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    def calibrate_baseline(self, baseline: Node) -> SeedCache:
        """Calibrate measure + seed caches on seeds 1,2,3 (locked)."""

        class _Recording:
            def __init__(self, inner: Any) -> None:
                self._inner = inner
                self.by_rung_seed: dict[tuple[str, int], float] = {}
                self.run_cfg = inner.run_cfg

            def run(self, node, rung, seed, timeout_s, **kwargs):  # noqa: ANN001
                res = self._inner.run(node, rung, seed, timeout_s, **kwargs)
                if res.ok and METRIC in res.metrics:
                    self.by_rung_seed[(str(rung), int(seed))] = float(
                        res.metrics[METRIC]
                    )
                return res

        recorder = _Recording(self.runner)
        self.measure.calibrate_from_runs(
            recorder,
            baseline,
            screen_seeds=list(SCREEN_SEEDS_CAL),
            full_seeds=list(FULL_SEEDS),
            fixed_pair=[SCREEN_SEED, SCREEN_SEED],
        )
        screen_scores = {
            s: recorder.by_rung_seed[("screen", s)] for s in SCREEN_SEEDS_CAL
        }
        full_scores = {
            s: recorder.by_rung_seed[("full", s)] for s in FULL_SEEDS
        }
        self.screen_inc = SeedCache(screen_scores)
        self.full_inc = SeedCache(full_scores)

        holdout_scores: dict[int, float] = {}
        for seed in HOLDOUT_SEEDS:
            res = self.runner.run(
                baseline, "holdout", seed=seed, timeout_s=self.full_timeout_s
            )
            if not res.ok:
                raise RuntimeError(f"baseline holdout seed {seed} failed")
            holdout_scores[seed] = float(res.metrics[METRIC])
        self.holdout_inc = SeedCache(holdout_scores)
        self._best_reported = statistics.mean(holdout_scores.values())

        self.incumbent = baseline
        self.nodes[baseline.id] = baseline
        return self.full_inc

    def _family_of(self, hyp: Hypothesis) -> str:
        return f"{hyp.stage}/{hyp.mechanism}"

    def _kind_for(self, hyp: Hypothesis) -> str:
        if hyp.id in self._preallocated:
            return "draft"
        if hyp.parent_node is None and "base" in hyp.id:
            return "draft"
        return "improve"

    def _maybe_fork(self, just_finished: Node) -> None:
        if just_finished.kind != "improve":
            return
        if just_finished.state == "promoted":
            self._stall = 0
            return
        self._stall += 1
        if self._stall < STALL_STEPS:
            return
        self._stall = 0
        log = self._read_log()
        stats = family_stats(log)
        incumb_fam = None
        if self.incumbent is not None:
            hid = self.incumbent.hypothesis_id
            hyp = self.hyp_index.get(hid)
            if hyp is not None:
                incumb_fam = self._family_of(hyp)

        def fam_score(fam: str) -> float:
            row = stats.get(fam)
            if not row or row.get("n", 0) == 0:
                # Cold-start: prefer families that still have unused hand hyps.
                return 0.0
            gpu = max(float(row["mean_gpu_min"]), 1e-9)
            return (float(row["mean_delta"]) + float(row["sd_delta"])) / gpu

        used_hyps = {n.hypothesis_id for n in self.nodes.values()}
        all_fams = {self._family_of(h) for h in self.hyp_index.values()}
        # Prefer families that still have an unused hypothesis; exclude incumbent.
        candidates = [
            f
            for f in all_fams
            if f != incumb_fam
            and any(
                self._family_of(h) == f and h.id not in used_hyps
                for h in self.hyp_index.values()
            )
        ]
        if not candidates:
            candidates = [f for f in all_fams if f != incumb_fam]
        families = sorted(candidates, key=lambda f: (-fam_score(f), f))

        parent = self.incumbent.id if self.incumbent else just_finished.id
        for fam in families[:2]:
            draft = None
            for h in self.hyp_index.values():
                if self._family_of(h) == fam and h.id not in used_hyps:
                    draft = h
                    break
            if draft is None:
                continue
            if draft.patch is None:
                continue
            if not self.queue.push(draft):
                continue
            nid = self.events.new_node(parent)
            self._preallocated[draft.id] = nid
            self.events.emit(
                "node_created",
                id=nid,
                parent=parent,
                kind="draft",
                hypothesis_id=draft.id,
                summary=f"node {nid} forked draft in {fam}",
            )
            self.nodes[nid] = Node(
                id=nid,
                parent=parent,
                hypothesis_id=draft.id,
                commit=None,
                state="screening",
                rung="smoke",
                kind="draft",
                scores={},
                seeds=[],
                cost=Cost(0.0, 0, 0, "training"),
                created_seq=nid,
            )
            used_hyps.add(draft.id)

    def _holdout_if_needed(self, node: Node, *, at_end: bool = False) -> None:
        if at_end:
            if self.measure._holdout_visits >= 2:  # noqa: SLF001
                return
            # Second visit at run end (only if first already happened, or force end visit).
            target = self.incumbent or node
            report = self.measure.holdout_report(
                target, self.runner, self.holdout_inc, self._best_reported
            )
            self._best_reported = report.best_reported
            return
        # First promotion only.
        if self._holdout_done_first:
            return
        report = self.measure.holdout_report(
            node, self.runner, self.holdout_inc, self._best_reported
        )
        self._best_reported = report.best_reported
        self._holdout_done_first = True

    def _run_ladder(self, node: Node, hyp: Hypothesis) -> None:
        family = self._family_of(hyp)
        diff_summary = hyp.description[:80]

        # smoke
        self._set_state(node, "running", f"node {node.id} smoke")
        smoke = self.runner.run(
            node, "smoke", seed=SCREEN_SEED, timeout_s=self.smoke_timeout_s
        )
        self._gpu_spent_s += float(smoke.wall_s)
        if not smoke.ok:
            self._handle_failure(node, hyp, smoke)
            return

        # screen (paired seed 1)
        screen = self.runner.run(
            node, "screen", seed=SCREEN_SEED, timeout_s=self.screen_timeout_s
        )
        self._gpu_spent_s += float(screen.wall_s)
        if not screen.ok:
            self._handle_failure(node, hyp, screen)
            return

        v_screen = self.measure.verdict(
            node,
            [screen],
            self.screen_inc,
            "screen",
            attribution=self.attribution,  # type: ignore[arg-type]
        )
        # Attach gpu_min onto a follow-up is not possible; family_stats defaults.

        if v_screen.state != "replicating":
            if node.state != v_screen.state:
                # verdict event already set state in app; keep Node in sync
                try:
                    transition(node, v_screen.state)
                except IllegalTransition:
                    node.state = v_screen.state  # type: ignore[assignment]
            else:
                node.state = v_screen.state  # type: ignore[assignment]
            if self.workspace is not None and self.incumbent and self.incumbent.commit:
                self.workspace.checkout(self.incumbent.commit)
            return

        try:
            transition(node, "replicating")
        except IllegalTransition:
            pass
        node.state = "replicating"  # type: ignore[assignment]
        self.events.emit(
            "state_changed",
            node=node.id,
            state="replicating",
            summary=f"node {node.id} → replicating",
        )

        results: list[RunResult] = []
        last_delta: float | None = None
        for seed in FULL_SEEDS:
            if self._live_count() > MAX_LIVE_BRANCHES:
                # Should not happen mid-ladder for a single node; belt-and-braces.
                break
            res = self.runner.run(
                node, "full", seed=seed, timeout_s=self.full_timeout_s
            )
            self._gpu_spent_s += float(res.wall_s)
            gpu_min = float(res.wall_s) / 60.0
            if not res.ok:
                self._handle_failure(node, hyp, res)
                return
            results.append(res)
            # Per-seed lesson line (spec: one line per full-rung run).
            try:
                d = float(res.metrics[METRIC]) - self.full_inc.get(seed)
            except Exception:
                d = None
            last_delta = d
            self._append_lesson(node, family, d, gpu_min, diff_summary)

        v_rep = self.measure.verdict(
            node,
            results,
            self.full_inc,
            "replicate",
            attribution=self.attribution,  # type: ignore[arg-type]
        )
        try:
            transition(node, v_rep.state)
        except IllegalTransition:
            node.state = v_rep.state  # type: ignore[assignment]
        else:
            # verdict already emitted state; emit state_changed only if needed
            pass
        node.state = v_rep.state  # type: ignore[assignment]

        if v_rep.state == "promoted":
            self._promotions += 1
            # Roll seed caches to this node's scores.
            screen_roll = dict(self.screen_inc.as_dict())
            screen_roll[SCREEN_SEED] = float(screen.metrics[METRIC])
            self.screen_inc = SeedCache(screen_roll)
            full_roll = {
                r.seed: float(r.metrics[METRIC]) for r in results
            }
            self.full_inc = SeedCache(full_roll)
            self.incumbent = node
            self._holdout_if_needed(node, at_end=False)
        else:
            if self.workspace is not None and self.incumbent and self.incumbent.commit:
                self.workspace.checkout(self.incumbent.commit)

        del last_delta
        self.measure.maybe_refresh()

    def _handle_failure(
        self, node: Node, hyp: Hypothesis, result: RunResult
    ) -> None:
        fc = result.failure_class or "crash"
        # Runner may already have emitted debugging; sync local state.
        parent = node.parent
        depth = 0
        if parent is not None:
            depth = self._debug_depth.get(parent, 0)
        if fc in ("crash", "contract_violation") and depth < DEBUG_DEPTH:
            self._debug_depth[node.id] = depth + 1
            if node.state != "debugging":
                try:
                    self._set_state(node, "debugging")
                except IllegalTransition:
                    node.state = "debugging"  # type: ignore[assignment]
            # Requeue a debug attempt via coder (phase 6 PatchCoder ignores traceback).
            try:
                self.coder.materialise(hyp, self.incumbent or node, result.stderr_tail)
            except Exception:
                pass
            debug_hyp = Hypothesis(
                id=f"{hyp.id}-debug-{node.id}",
                stage=hyp.stage,
                mechanism=hyp.mechanism,
                description=hyp.description,
                citation=hyp.citation,
                expected_gain=hyp.expected_gain,
                expected_gpu_h=hyp.expected_gpu_h,
                parent_node=node.id,
                patch=hyp.patch,
            )
            self.hyp_index[debug_hyp.id] = debug_hyp
            self.queue.push(debug_hyp)
            # Leave the crashed node in debugging; the retry is a new queue item.
        else:
            try:
                if node.state == "debugging":
                    self._set_state(node, "retired")
                elif node.state in ("running", "replicating", "screening"):
                    self._set_state(node, "retired")
                else:
                    node.state = "retired"  # type: ignore[assignment]
            except IllegalTransition:
                node.state = "retired"  # type: ignore[assignment]
        if self.workspace is not None and self.incumbent and self.incumbent.commit:
            self.workspace.checkout(self.incumbent.commit)

    def step(self) -> bool:
        if self._ended:
            return False
        if self._nodes_done >= self.max_nodes:
            self._finish("max_nodes")
            return False
        if self.budget is not None:
            try:
                limit_h = float(self.budget)
            except (TypeError, ValueError):
                limit_h = None
            if limit_h is not None and self._gpu_spent_s / 3600.0 >= limit_h:
                self._finish("budget")
                return False
        if len(self.queue) == 0:
            self._finish("empty_queue")
            return False
        if self._live_count() >= MAX_LIVE_BRANCHES:
            # Cannot start another; stop rather than spin.
            self._finish("max_live_branches")
            return False

        hyp = self.queue.pop()
        self.hyp_index.setdefault(hyp.id, hyp)

        parent = hyp.parent_node
        if parent is None and self.incumbent is not None:
            parent = self.incumbent.id

        if hyp.id in self._preallocated:
            nid = self._preallocated.pop(hyp.id)
            node = self.nodes[nid]
            kind = "draft"
        else:
            nid = self.events.new_node(parent)
            kind = self._kind_for(hyp)
            self.events.emit(
                "node_created",
                id=nid,
                parent=parent,
                kind=kind,
                hypothesis_id=hyp.id,
                summary=f"node {nid} created as {kind}",
            )
            node = Node(
                id=nid,
                parent=parent,
                hypothesis_id=hyp.id,
                commit=None,
                state="screening",
                rung="smoke",
                kind=kind,  # type: ignore[arg-type]
                scores={},
                seeds=[],
                cost=Cost(0.0, 0, 0, "training"),
                created_seq=nid,
            )
            self.nodes[nid] = node

        # Materialise + commit patch into workspace (from pristine template —
        # hand patches are absolute FEATURES line edits, not stacked diffs).
        if self.workspace is not None:
            if self._initial_commit:
                self.workspace.checkout(self._initial_commit)
            try:
                diff_path = self.coder.materialise(
                    hyp, self.incumbent or node, None
                )
            except Exception:
                diff_path = hyp.patch
            if diff_path is not None:
                sha = self.workspace.commit_node(nid, Path(diff_path))
                node.commit = sha

        self._nodes_done += 1
        self._run_ladder(node, hyp)
        self._maybe_fork(node)

        # Rerank after every verdict-bearing step.
        stats = family_stats(self._read_log())
        if self.queue:
            self.queue.rerank(stats)
        return True

    def _finish(self, reason: str) -> None:
        if self._ended:
            return
        self._ended = True
        if self.incumbent is not None:
            try:
                self._holdout_if_needed(self.incumbent, at_end=True)
            except Exception:
                pass
        inc_id = self.incumbent.id if self.incumbent else None
        counts = {
            "nodes": len(self.nodes),
            "promotions": self._promotions,
            "queue_left": len(self.queue),
        }
        self.events.emit(
            "run_ended",
            reason=reason,
            incumbent=inc_id,
            counts=counts,
            summary=(
                f"run ended ({reason}); incumbent={inc_id}; "
                f"nodes={counts['nodes']} promotions={counts['promotions']}"
            ),
        )

    def run(self) -> None:
        while self.step():
            pass
        if not self._ended:
            self._finish("empty_queue")
