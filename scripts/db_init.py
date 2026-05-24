#!/usr/bin/env python3
"""Initialize app DB (and optional LangGraph Postgres tables)."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_stack.runtime.checkpointer import get_checkpointer
from agent_stack.runtime.storage import get_engine, init_db
from agent_stack.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report schema status only")
    args = parser.parse_args()
    settings = load_settings()
    engine = get_engine(settings)
    schema = Path(__file__).resolve().parents[1] / "scripts" / "sql" / "app_schema.sql"
    init_db(engine, schema)
    print(f"Initialized app DB at {settings.app_database_url}")
    if settings.use_langgraph and settings.langgraph_checkpointer == "postgres":
        cp = get_checkpointer(settings)
        if cp is not None and hasattr(cp, "setup"):
            cp.setup()
            print("Initialized LangGraph Postgres checkpoint tables")
    if args.check:
        print("schema check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
