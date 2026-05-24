#!/usr/bin/env python3
"""Generate AGENTS.md and .well-known agent cards from local registry files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_stack.registry.agent_card import build_agent_card
from agent_stack.registry.config import ConfigError, load_all
from agent_stack.registry.instructions import build_agents_md


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repo root containing private yaml files")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        config = load_all(root)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1

    card = build_agent_card(config)
    agents_md = build_agents_md(config)

    well_known = root / ".well-known"
    well_known.mkdir(parents=True, exist_ok=True)
    for rel in config.agents.runtime.generated_card_paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(card, indent=2) + "\n")
        print(f"Generated {rel}")

    (root / "AGENTS.md").write_text(agents_md)
    print("Generated AGENTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
