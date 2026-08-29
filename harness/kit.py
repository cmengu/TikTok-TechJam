"""Single seam to the organisers' kuairand-starter-kit on disk."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

KIT_DIR = Path(os.environ.get("KIT_DIR", "~/Downloads/kuairand-starter-kit")).expanduser()

# Top-level kit modules (data.py, evaluate.py, submit.py) share names with our packages.
_KIT_MODULE_FILES = {
    "data": "data.py",
    "evaluate": "evaluate.py",
    "submit": "submit.py",
}


def kit_module(name: str):
    """Import a module from the kit directory (e.g. ``data``, ``evaluate``, ``submit``)."""
    if name in _KIT_MODULE_FILES:
        path = KIT_DIR / _KIT_MODULE_FILES[name]
        tag = f"_kuairand_kit_{name}"
        if tag in sys.modules:
            return sys.modules[tag]
        spec = importlib.util.spec_from_file_location(tag, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load kit module {name} from {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[tag] = mod
        spec.loader.exec_module(mod)
        return mod

    kit_path = str(KIT_DIR.resolve())
    if kit_path not in sys.path:
        sys.path.insert(0, kit_path)
    return importlib.import_module(name)
