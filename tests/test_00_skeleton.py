"""Phase 0 gate: skeleton imports, types, vocab, protocols, stubs."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import pkgutil
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest
import yaml

from harness.types import (
    EVENT_TYPES,
    STATES,
    Cost,
    Hypothesis,
    Node,
    RunResult,
    Verdict,
)

ROOT = Path(__file__).resolve().parents[1]

# Modules whose stubs have been replaced by a real implementation.
# Each phase PR extends this set; stubs outside it must still raise.
IMPLEMENTED = {
    "harness.protocol",
    "harness.events",
    "harness.fake_run",
    "app.server",
}

PRODUCT_STATES = {
    "screening",
    "running",
    "replicating",
    "promoted",
    "inconclusive",
    "rejected",
    "retired",
    "leaked",
    "debugging",
}

VOCAB_EVENT_TYPES = (
    "run_started",
    "node_created",
    "state_changed",
    "heartbeat",
    "measurement",
    "verdict",
    "failure",
    "recovery",
    "rule_trip",
    "research_source",
    "cache_lookup",
    "hypothesis_queued",
    "queue_reordered",
    "submission_written",
    "intervention",
    "run_ended",
)

# Harness Decisions §1 — the seven fields that stay null until the webinar.
ALICCP_NULL_PATHS = {
    ("ruler", "baseline", "published", "ctr_auc"),
    ("ruler", "baseline", "published", "cvr_auc"),
    ("ruler", "convergence", "epsilon"),
    ("ruler", "convergence", "n_rounds"),
    ("run", "budget", "gpu_hours"),
    ("run", "budget", "wall_clock_h"),
    ("run", "budget", "llm_usd"),
}


def _walk_null_paths(obj, prefix=()) -> set[tuple]:
    found: set[tuple] = set()
    if obj is None:
        found.add(prefix)
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found |= _walk_null_paths(v, prefix + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found |= _walk_null_paths(v, prefix + (i,))
    return found


def _nulls_under(obj) -> set[tuple]:
    return _walk_null_paths(obj)


def _jsonable(obj):
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return {f.name: _jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _from_jsonable(cls, data):
    kwargs = {}
    for f in fields(cls):
        val = data[f.name]
        if f.name in {"patch", "result_path", "checkpoint_path"} and val is not None:
            val = Path(val)
        elif f.name == "cost" and isinstance(val, dict):
            val = Cost(**val)
        elif f.name == "band" and isinstance(val, list):
            val = tuple(val)
        kwargs[f.name] = val
    return cls(**kwargs)


def test_every_module_imports():
    packages = ["data", "harness", "app"]
    imported = []
    for name in packages:
        pkg = importlib.import_module(name) if name != "app" else None
        if name == "app":
            # app/ has no __init__.py; load server by path-derived name.
            spec = importlib.util.spec_from_file_location(
                "app.server", ROOT / "app" / "server.py"
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            imported.append("app.server")
            continue
        for modinfo in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            importlib.import_module(modinfo.name)
            imported.append(modinfo.name)
    assert imported


def test_types_round_trip():
    cost = Cost(gpu_s=1.5, tokens_in=10, tokens_out=20, slice="training")
    hyp = Hypothesis(
        id="h1",
        stage="features",
        mechanism="target-encoding",
        description="encode categoricals",
        citation="no prior",
        expected_gain=0.01,
        expected_gpu_h=0.1,
        parent_node=None,
        patch=Path("hypotheses/patches/base.diff"),
    )
    node = Node(
        id=1,
        parent=None,
        hypothesis_id="h1",
        commit="abc",
        state="screening",
        rung="screen",
        kind="draft",
        scores={"cvr_auc": [0.5]},
        seeds=[1],
        cost=cost,
        created_seq=1,
    )
    result = RunResult(
        node=1,
        attempt=1,
        seed=1,
        rung="screen",
        ok=True,
        metrics={"cvr_auc": 0.5},
        failure_class=None,
        stderr_tail="",
        gpu_s=1.0,
        wall_s=2.0,
        result_path=Path("result.json"),
        checkpoint_path=None,
    )
    verdict = Verdict(
        node=1,
        rung="screen",
        state="inconclusive",
        metric="cvr_auc",
        delta_mean=0.0,
        delta_per_seed=[0.0],
        band=(-0.01, 0.01),
        reason="within band",
        rule_trips=[],
    )
    for obj in (hyp, node, result, verdict):
        payload = json.dumps(_jsonable(obj))
        rebuilt = _from_jsonable(type(obj), json.loads(payload))
        assert _jsonable(rebuilt) == json.loads(payload)
        assert _jsonable(rebuilt) == _jsonable(obj)


def test_state_vocabulary():
    assert set(STATES) == PRODUCT_STATES
    assert len(EVENT_TYPES) == 16
    assert EVENT_TYPES == VOCAB_EVENT_TYPES


def test_protocol_files_parse():
    synthetic = yaml.safe_load((ROOT / "protocols" / "synthetic.yaml").read_text())
    aliccp = yaml.safe_load((ROOT / "protocols" / "aliccp.yaml").read_text())
    assert _nulls_under(synthetic["ruler"]) == set()
    nulls = _nulls_under(aliccp)
    assert nulls == ALICCP_NULL_PATHS
    assert len(nulls) == 7


def _stub_callables():
    """Collect stub callables under data/, harness/, app/ that must raise."""
    skip_modules = {
        "harness.types",
        "harness",
        "harness.candidate",
        "harness.agents",
        "harness.tasks",
        "data",
    }
    found = []
    for package in ("data", "harness"):
        pkg = importlib.import_module(package)
        for modinfo in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            if (
                modinfo.name in skip_modules
                or modinfo.name in IMPLEMENTED
                or modinfo.name.endswith(".__main__")
            ):
                continue
            mod = importlib.import_module(modinfo.name)
            for name, obj in inspect.getmembers(mod, inspect.isfunction):
                if obj.__module__ != mod.__name__:
                    continue
                if name.startswith("_"):
                    continue
                found.append(("fn", modinfo.name, name, obj))
            for name, cls in inspect.getmembers(mod, inspect.isclass):
                if cls.__module__ != mod.__name__:
                    continue
                if is_dataclass(cls):
                    continue
                # typing.Protocol subclasses: skip abstract interface bodies
                if getattr(cls, "_is_protocol", False):
                    continue
                for meth_name, descr in cls.__dict__.items():
                    if isinstance(descr, staticmethod):
                        found.append(
                            (
                                "static",
                                modinfo.name,
                                f"{name}.{meth_name}",
                                descr.__func__,
                                cls,
                            )
                        )
                        continue
                    if isinstance(descr, classmethod):
                        continue
                    if meth_name.startswith("_") and meth_name != "__init__":
                        continue
                    if not inspect.isfunction(descr):
                        continue
                    if meth_name == "__init__" and descr is object.__init__:
                        continue
                    found.append(
                        ("meth", modinfo.name, f"{name}.{meth_name}", descr, cls)
                    )
    # app.server
    if "app.server" not in IMPLEMENTED:
        spec = importlib.util.spec_from_file_location(
            "app.server", ROOT / "app" / "server.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if obj.__module__ == mod.__name__ and not name.startswith("_"):
                found.append(("fn", "app.server", name, obj))
    return found


def _required_arg_count(fn, skip_self: bool = False) -> int:
    params = list(inspect.signature(fn).parameters.values())
    if skip_self and params:
        params = params[1:]
    return sum(
        1
        for p in params
        if p.default is inspect.Parameter.empty
        and p.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    )


def test_stubs_raise():
    for item in _stub_callables():
        kind = item[0]
        if kind == "fn":
            _, _modname, _name, fn = item
            with pytest.raises(NotImplementedError):
                fn(*([None] * _required_arg_count(fn)))
        elif kind == "static":
            _, _modname, _qual, fn, _cls = item
            with pytest.raises(NotImplementedError):
                fn(*([None] * _required_arg_count(fn)))
        else:
            _, _modname, qual, meth, cls = item
            if qual.endswith(".__init__"):
                with pytest.raises(NotImplementedError):
                    cls(*([None] * _required_arg_count(meth, skip_self=True)))
                continue
            init = getattr(cls, "__init__", None)
            init_raises = False
            if init is not None and init is not object.__init__:
                try:
                    init_raises = "raise NotImplementedError" in inspect.getsource(init)
                except OSError:
                    init_raises = True
            if init_raises:
                continue
            inst = cls()
            with pytest.raises(NotImplementedError):
                getattr(inst, meth.__name__)(
                    *([None] * _required_arg_count(meth, skip_self=True))
                )
