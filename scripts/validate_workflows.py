#!/usr/bin/env python3
"""Validate workflows.yaml against the registry loader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_stack.registry.config import ConfigError, load_all


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="workflows.yaml")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        load_all(root)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
