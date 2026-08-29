"""Single seam to the organisers' kuairand-starter-kit on disk."""

from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path

KIT_DIR = Path(os.environ.get("KIT_DIR", "~/Downloads/kuairand-starter-kit")).expanduser()

_KIT_MODULE_FILES = {
    "data": "data.py",
    "evaluate": "evaluate.py",
    "submit": "submit.py",
    "baseline": "baseline.py",
}
_KIT_TAG = "_kuairand_kit_{name}"


@contextmanager
def _kit_import_context():
    """Kit modules do ``from data import …``; shadow our ``data`` package briefly."""
    saved_data = sys.modules.get("data")
    sys.modules["data"] = _load_kit_file("data", _in_context=True)
    kit_path = str(KIT_DIR.resolve())
    old_path = list(sys.path)
    if kit_path not in sys.path:
        sys.path.insert(0, kit_path)
    try:
        yield
    finally:
        sys.path[:] = old_path
        if saved_data is None:
            sys.modules.pop("data", None)
        else:
            sys.modules["data"] = saved_data


def _load_kit_file(name: str, *, _in_context: bool = False):
    tag = _KIT_TAG.format(name=name)
    if tag in sys.modules:
        return sys.modules[tag]
    path = KIT_DIR / _KIT_MODULE_FILES[name]
    spec = importlib.util.spec_from_file_location(tag, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load kit module {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[tag] = mod
    if name == "data" or _in_context:
        spec.loader.exec_module(mod)
    else:
        with _kit_import_context():
            spec.loader.exec_module(mod)
    return mod


def kit_module(name: str):
    """Import a module from the kit directory (e.g. ``data``, ``evaluate``, ``submit``)."""
    if name not in _KIT_MODULE_FILES:
        raise KeyError(f"unknown kit module: {name}")
    return _load_kit_file(name)
