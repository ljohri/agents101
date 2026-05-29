"""Command-line utility for talking to a running root planner agent.

Examples:
    root-agent agents
    root-agent commands
    root-agent status
    root-agent ask "find open-access PDFs for ./data/paper.pdf" --input pdf_path=./data/paper.pdf
    root-agent remember --local "PDFs live under ./artifacts"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

DEFAULT_URL = os.getenv("ROOT_AGENT_URL", "https://127.0.0.1:8443")


def _client(args: argparse.Namespace) -> httpx.Client:
    # --insecure allows local self-signed TLS during development.
    return httpx.Client(base_url=args.url, verify=not args.insecure, timeout=120.0)


def _parse_inputs(pairs: list[str]) -> dict:
    """Turn ``k=v`` pairs into a dict (values are kept as strings)."""
    out: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--input must be k=v, got {pair!r}")
        key, value = pair.split("=", 1)
        out[key] = value
    return out


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=False))


def cmd_agents(args: argparse.Namespace) -> int:
    with _client(args) as c:
        data = c.get("/agents").json()
    for a in data.get("agents", []):
        flag = "UP  " if a.get("status") == "up" else "DOWN"
        print(f"[{flag}] {a.get('id'):20} {a.get('endpoint'):24} skills={len(a.get('skills', []))}")
    if not data.get("agents"):
        print("(no agents visible — is the runtime up?)")
    return 0


def cmd_commands(args: argparse.Namespace) -> int:
    with _client(args) as c:
        data = c.get("/commands").json()
    for cmd in data.get("commands", []):
        flag = "OK  " if cmd.get("available") else "N/A "
        miss = f" missing={cmd['missing_binaries']}" if cmd.get("missing_binaries") else ""
        print(f"[{flag}] {cmd.get('name'):20} {cmd.get('description', '')}{miss}")
    if not data.get("commands"):
        print("(no command recipes configured)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    with _client(args) as c:
        _print(c.get("/status").json())
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    payload = {
        "request": args.request,
        "inputs": _parse_inputs(args.input),
        "conversation_id": args.conversation,
    }
    with _client(args) as c:
        resp = c.post("/invoke", json=payload).json()
    _print(resp)
    return 0 if resp.get("ok") else 1


def cmd_remember(args: argparse.Namespace) -> int:
    tier = "global"
    if args.local:
        tier = "local"
    elif args.session:
        tier = "session"
    with _client(args) as c:
        resp = c.post(
            "/memory",
            json={"tier": tier, "note": args.note, "conversation_id": args.conversation},
        ).json()
    _print(resp)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="root-agent", description="Talk to a running root planner agent.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"root agent base URL (default {DEFAULT_URL})")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed dev certs)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("agents", help="list visible agents and up/down status").set_defaults(func=cmd_agents)
    sub.add_parser("commands", help="list global commands and availability").set_defaults(func=cmd_commands)
    sub.add_parser("status", help="show root agent status").set_defaults(func=cmd_status)

    p_ask = sub.add_parser("ask", help="send a request to the planner")
    p_ask.add_argument("request", help="the natural-language request")
    p_ask.add_argument("--input", action="append", default=[], help="k=v input (repeatable)")
    p_ask.add_argument("--conversation", default=None, help="conversation id for memory continuity")
    p_ask.set_defaults(func=cmd_ask)

    p_rem = sub.add_parser("remember", help="append a memory note")
    p_rem.add_argument("note", help="the note to remember")
    p_rem.add_argument("--global", dest="global_", action="store_true", help="global tier (default)")
    p_rem.add_argument("--local", action="store_true", help="local/project tier")
    p_rem.add_argument("--session", action="store_true", help="session tier (requires --conversation)")
    p_rem.add_argument("--conversation", default=None, help="conversation id for session memory")
    p_rem.set_defaults(func=cmd_remember)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except httpx.HTTPError as exc:
        print(f"error: could not reach root agent at {args.url}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
