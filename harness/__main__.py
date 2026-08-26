"""CLI dispatcher. Phase 1 wires ``init``; later phases add ``fake``, ``run``, etc."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    print("not implemented")
    raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
