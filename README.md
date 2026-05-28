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
uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8086
```

Edit `workflows.yaml` and `agents.yaml` freely — they never appear in git status.

## Where to start

- **Build plan:** [`docs/build-plan.md`](docs/build-plan.md)
- **Architecture:** [`docs/architecture/00-overview.md`](docs/architecture/00-overview.md)
- **Cookbook:** [`docs/architecture/12-extension-cookbook.md`](docs/architecture/12-extension-cookbook.md)

## Quick test

```bash
uv run pytest -m "not chaos"
curl -fsS http://127.0.0.1:8086/healthz
curl -fsS -X POST http://127.0.0.1:8086/a2a/generic \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"skill":"echo","inputs":{"message":"hi"}}}'
```

## Tracing (OTEL + Jaeger/Tempo)

Start one local trace backend:

```bash
docker compose -f docker-compose.jaeger.yml up -d
# or:
docker compose -f docker-compose.observability.yml up -d
```

Run the app with OTEL enabled (defaults already present in `.env.example`):

```bash
cp .env.example .env
uv sync --extra dev --extra otel
uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8086
```

Trigger a workflow call with a known trace id:

```bash
curl -s -X POST http://127.0.0.1:8086/a2a/workflows \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer dev-token' \
  -d '{
    "jsonrpc":"2.0",
    "id":"1",
    "method":"message/send",
    "params":{
      "skill":"bibliography-research",
      "inputs":{"pdf_path":"./data/paper.pdf"},
      "metadata":{"trace_id":"0123456789abcdef0123456789abcdef"}
    }
  }'
```

Explore traces:

- Jaeger UI: `http://127.0.0.1:16686`
- Grafana Explore (Tempo): `http://127.0.0.1:3000` (default login `admin/admin`)
