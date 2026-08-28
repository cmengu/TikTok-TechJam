"""Phase 7: Optuna screen-rung knob tuner."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from optuna.trial import TrialState

from harness.agents._util import cost_dict
from harness.types import Cost, Hypothesis, Node

HAND_CONFIGS = (
    {"lr": 5e-4, "emb": 12, "dropout": 0.1},
    {"lr": 2e-3, "emb": 8, "dropout": 0.0},
)


def _hand_hypothesis(node: Node, knobs: dict[str, Any], idx: int) -> Hypothesis:
    return Hypothesis(
        id=f"tune-hand-{node.id}-{idx}",
        stage="training",
        mechanism="knobs",
        description=f"hand knob config {knobs}",
        citation="no prior",
        expected_gain=0.0,
        expected_gpu_h=0.05,
        parent_node=node.id,
        patch=None,
    )


def tune(
    node: Node,
    knob_space: dict[str, tuple],
    runner,
    events,
    budget: int,
    screen_seed: int,
) -> list[Hypothesis]:
    """Screen-rung tuner; budget < 10 skips Optuna study."""
    run_dir = Path(runner.run_cfg["run_dir"])
    incumbent = {
        "lr": float(runner.run_cfg.get("lr", 1e-3)),
        "emb": int(runner.run_cfg.get("emb", 16)),
        "dropout": float(runner.run_cfg.get("dropout", 0.0)),
    }

    def _run_trial(knobs: dict[str, Any], label: str) -> float | None:
        trial_id = events.new_node(node.id)
        events.emit(
            "node_created",
            id=trial_id,
            parent=node.id,
            kind="trial",
            hypothesis_id=label,
            summary=f"trial node {trial_id} parent={node.id}",
        )
        saved = dict(runner.run_cfg)
        runner.run_cfg.update(
            {
                "lr": str(knobs["lr"]),
                "emb": knobs["emb"],
                "dropout": knobs.get("dropout", 0.0),
            }
        )
        try:
            result = runner.run(
                Node(
                    id=trial_id,
                    parent=node.id,
                    hypothesis_id=label,
                    commit=None,
                    state="running",
                    rung="screen",
                    kind="trial",
                    scores={},
                    seeds=[screen_seed],
                    cost=Cost(0.0, 0, 0, "tuning"),
                    created_seq=trial_id,
                ),
                "screen",
                screen_seed,
                float(runner.run_cfg.get("timeout_s", 300.0)),
            )
        finally:
            runner.run_cfg.clear()
            runner.run_cfg.update(saved)

        events.emit(
            "measurement",
            node=trial_id,
            parent=node.id,
            cost=cost_dict(Cost(result.gpu_s, 0, 0, "tuning")),
            summary=f"trial {trial_id} screen seed {screen_seed}",
        )
        if not result.ok:
            return None
        return float(result.metrics.get("cvr_auc", 0.0))

    if budget < 10:
        scores: list[tuple[float, dict[str, Any]]] = []
        for i, knobs in enumerate((incumbent, *HAND_CONFIGS[:2])):
            val = _run_trial(knobs, f"tune-budget-{node.id}-{i}")
            if val is not None:
                scores.append((val, knobs))
        scores.sort(key=lambda x: -x[0])
        return [
            _hand_hypothesis(node, knobs, i) for i, (_, knobs) in enumerate(scores[:3])
        ]

    journal = run_dir / f"optuna-node-{node.id}.log"
    storage = JournalStorage(JournalFileBackend(str(journal)))
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.GPSampler(n_startup_trials=5),
        storage=storage,
        study_name=f"node-{node.id}",
        load_if_exists=True,
    )
    study.enqueue_trial(incumbent)

    for _ in range(budget):
        trial = study.ask()
        lr = trial.suggest_float("lr", 1e-4, 1e-2, log=True)
        emb = trial.suggest_int("emb", 4, 32, step=4)
        dropout = trial.suggest_float("dropout", 0.0, 0.5)
        knobs = {"lr": lr, "emb": emb, "dropout": dropout}
        trial.set_user_attr("seed", screen_seed)
        val = _run_trial(knobs, f"tune-{node.id}-{trial.number}")
        if val is None:
            study.tell(trial, state=TrialState.FAIL)
        else:
            study.tell(trial, val)

    ranked = sorted(
        (t for t in study.trials if t.value is not None and t.state == TrialState.COMPLETE),
        key=lambda t: -float(t.value),
    )[:3]
    out: list[Hypothesis] = []
    for i, trial in enumerate(ranked):
        params = dict(trial.params)
        out.append(_hand_hypothesis(node, params, i))
    return out
