#!/usr/bin/env python3
"""Validate an agent card JSON file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SECRET_PATTERN = re.compile(
    r"(token|secret|password|api_key|private_key|refresh_token|client_secret|service_account|bearer|credentials)",
    re.I,
)


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SECRET_PATTERN.search(str(k)):
                print(f"secret-looking key at {path}.{k}", file=sys.stderr)
                return False
            if not _walk(v, f"{path}.{k}"):
                return False
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if not _walk(v, f"{path}[{i}]"):
                return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    data = json.loads(args.path.read_text())
    for field in ("name", "description", "url", "skills"):
        if field not in data:
            print(f"missing {field}", file=sys.stderr)
            return 1
    if not data["skills"]:
        print("skills must be non-empty", file=sys.stderr)
        return 1
    for skill in data["skills"]:
        for req in ("id", "name", "description"):
            if req not in skill:
                print(f"skill missing {req}", file=sys.stderr)
                return 1
    if not _walk(data):
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
