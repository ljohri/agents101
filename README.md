# agents101 — Workflow-Driven Local Agent Stack

A local agent runtime where **MCP tools**, **A2A agent skills**, and **declarative workflows** share one capability model.

## Private config (not pushed to GitHub)

Your real agent and workflow definitions stay local:

| Private (gitignored) | Committed sample |
|---------------------|------------------|
| `agents.yaml` | `agents.yaml.example` |
| `workflows.yaml` | `workflows.yaml.example` |
| `mcp_servers.yaml` | `mcp_servers.yaml.example` |
| `AGENTS.md`, `.well-known/*` | generated locally from your private YAML |

First-time setup:

```bash
bash scripts/bootstrap_local_config.sh   # copies *.example → private files
cp .env.example .env                     # if needed
uv sync --extra dev
uv run python scripts/generate_agent_artifacts.py
uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8080
```

Edit `workflows.yaml` and `agents.yaml` freely — they never appear in git status.

## Where to start

- **Build plan:** [`docs/build-plan.md`](docs/build-plan.md)
- **Architecture:** [`docs/architecture/00-overview.md`](docs/architecture/00-overview.md)
- **Cookbook:** [`docs/architecture/12-extension-cookbook.md`](docs/architecture/12-extension-cookbook.md)

## Quick test

```bash
uv run pytest -m "not chaos"
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS -X POST http://127.0.0.1:8080/a2a/generic \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"skill":"echo","inputs":{"message":"hi"}}}'
```
