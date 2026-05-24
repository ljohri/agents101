> **SUPERSEDED.** This plan is kept for traceability. The canonical build plan is [`docs/build-plan.md`](../build-plan.md), with architectural detail in [`docs/architecture/`](../architecture/). Differences vs. this legacy plan are summarized in section 9 ("Detailed remediation of weaknesses") of the new build plan.

---

# Cursor Implementation Instructions: OpenClaw + NemoClaw + A2A + Agent Card + LangGraph Runtime

Version: 0.2 tightened
Target audience: Cursor Agent / coding agent
Primary goal: Build a local, file-driven agent runtime where agent metadata is defined once in `agents.yaml`, A2A cards are generated from it, and non-trivial agents run through a shared LangGraph-capable runtime.

---

## 0. Executive Design

Build a **shared local agent runtime**. Do not embed A2A, LangGraph, storage, auth, audit, and OpenClaw/NemoClaw plumbing separately inside each agent.

Use this separation:

```text
agents.yaml
→ canonical registry/config source
→ name, version, endpoint, skills, graph module, auth mode, policy metadata

AGENTS.md
→ internal operating instructions
→ read by OpenClaw/Cursor/Claude-like coding agents
→ behavior, rules, workflows, filesystem policy

A2A Agent Card
→ external discovery contract
→ read by other agents/clients/registries
→ name, description, endpoint, capabilities, auth scheme, skills

Shared runtime
→ common infrastructure
→ A2A server, auth, routing, graph runner, checkpointer, audit, storage, OpenClaw bridge

Per-agent module
→ domain-specific logic only
→ state schema, LangGraph graph, prompts, tools, tests

OpenClaw
→ local agent shell / MCP and operator interface

NemoClaw
→ sandbox / OpenShell containment / policy boundary

LangGraph
→ optional but recommended internal workflow engine for stateful agents
→ checkpoint/resume/intermediate state/human approval

Postgres / SQLite
→ Postgres for production checkpoints and audit
→ SQLite for local bootstrap/dev
```

Core architecture:

```text
                       ┌────────────────────────────┐
                       │        agents.yaml         │
                       │ canonical local registry   │
                       └──────────────┬─────────────┘
                                      │
               ┌──────────────────────┼──────────────────────┐
               │                      │                      │
               ▼                      ▼                      ▼
        ┌─────────────┐       ┌──────────────┐       ┌────────────────┐
        │ AGENTS.md   │       │ A2A Card(s)  │       │ Runtime config │
        │ behavior    │       │ discovery    │       │ routing/policy │
        └─────────────┘       └──────┬───────┘       └───────┬────────┘
                                      │                       │
                                      ▼                       ▼
                         ┌────────────────────────────────────────┐
                         │ Shared Local Agent Runtime             │
                         │ FastAPI + A2A + auth + graph runner    │
                         │ audit + storage + OpenClaw/MCP bridge  │
                         └──────────────────┬─────────────────────┘
                                            │
                      ┌─────────────────────┼─────────────────────┐
                      │                     │                     │
                      ▼                     ▼                     ▼
             ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
             │ bib_agent      │    │ code_agent     │    │ generic_agent  │
             │ graph/state    │    │ graph/state    │    │ generic graph  │
             └───────┬────────┘    └───────┬────────┘    └───────┬────────┘
                     │                     │                     │
                     └──────────────┬──────┴──────────────┬──────┘
                                    ▼                     ▼
                         ┌──────────────────┐    ┌──────────────────┐
                         │ LangGraph        │    │ OpenClaw / MCP    │
                         │ checkpoints      │    │ tools/runtime     │
                         └────────┬─────────┘    └────────┬─────────┘
                                  ▼                       ▼
                         ┌────────────────────────────────────────┐
                         │ NemoClaw / OpenShell sandbox            │
                         │ process, network, credential boundary   │
                         └────────────────────────────────────────┘
```

---

## 1. Key Design Decisions

### 1.1 `AGENTS.md` and A2A Agent Card are not duplicates

They intentionally overlap only on high-level identity and skill names.

| Artifact | Audience | Purpose | Contains secrets? |
|---|---|---|---|
| `agents.yaml` | runtime + generator | canonical metadata and routing | no |
| `AGENTS.md` | agent/runtime/coding assistant | behavior and operating rules | no |
| `.well-known/agent-card.json` | external agents/clients | discovery and invocation contract | no |
| LangGraph checkpoint state | runtime | per-task/per-thread working state | no secrets by default |
| app DB audit tables | operator/admin | reporting, billing, audit, governance | no raw secrets |

### 1.2 Use a shared runtime

Do this:

```text
runtime/
→ A2A server
→ auth
→ graph runner
→ checkpointer
→ audit logger
→ OpenClaw/MCP bridge
→ config loader
→ artifact generation
```

Do **not** do this:

```text
bib_agent embeds its own A2A server
code_agent embeds its own A2A server
ops_agent embeds its own A2A server
```

Each serious agent should provide a graph definition, not duplicate runtime plumbing.

### 1.3 LangGraph placement

LangGraph sits **inside the shared runtime execution path**.

```text
A2A request
→ shared A2A handler
→ agent lookup from agents.yaml
→ graph module import
→ graph runner
→ LangGraph checkpointed execution
→ A2A response
```

LangGraph does not replace:

- A2A discovery
- MCP tool discovery
- OpenClaw
- NemoClaw
- app audit tables
- enterprise catalog

### 1.4 Storage recommendation

Use both LangGraph checkpoint storage and normal app tables.

```text
LangGraph Postgres checkpointer
→ execution state, checkpoints, resumes, interrupts, time travel

Application DB tables
→ conversations, messages, tool calls, approvals, artifacts, audit events
```

Do not rely only on LangGraph checkpoint tables for billing, reporting, governance, or admin UI.

---

## 2. Target Repository Layout

Create this structure:

```text
local-agent-stack/
  README.md
  pyproject.toml
  uv.lock
  .env.example
  .gitignore

  agents.yaml
  AGENTS.md                         # generated from agents.yaml, or curated with generated header

  .well-known/
    agent-card.json                 # generated
    agent.json                      # generated compatibility alias

  src/
    local_agent_stack/
      __init__.py
      main.py                       # FastAPI entrypoint

      runtime/
        __init__.py
        a2a_server.py               # shared A2A handling
        graph_runner.py             # shared LangGraph invocation
        checkpointer.py             # SQLite/Postgres checkpointer factory
        audit.py                    # app audit logger
        storage.py                  # app DB tables
        security.py                 # bearer token/dev auth
        mcp_bridge.py               # MCP bridge abstraction
        openclaw_bridge.py          # OpenClaw adapter
        artifacts.py                # artifact storage helpers

      registry/
        __init__.py
        config.py                   # agents.yaml loader
        schemas.py                  # Pydantic models
        agent_card.py               # A2A card generation
        instructions.py             # AGENTS.md generation
        loader.py                   # dynamic agent module loading

      agents/
        __init__.py

        generic_agent/
          __init__.py
          AGENTS.md
          state.py
          graph.py
          prompts.py
          tools.py

        bibliography_agent/
          __init__.py
          AGENTS.md
          state.py
          graph.py
          prompts.py
          tools.py

      tools/
        __init__.py
        echo.py
        filesystem_safe.py

  scripts/
    generate_agent_artifacts.py
    validate_agent_card.py
    run_local.sh
    openclaw_check.sh
    run_in_nemoclaw.sh
    db_init.py

  docs/
    architecture.md
    a2a.md
    agents_yaml.md
    openclaw.md
    nemoclaw.md
    langgraph.md
    storage.md
    security.md
    cursor_tasks.md

  tests/
    test_agents_yaml.py
    test_agent_card_generation.py
    test_agents_md_generation.py
    test_a2a_discovery.py
    test_a2a_methods.py
    test_storage.py
    test_graph_runner.py
```

---

## 3. Python Project Setup

Use `uv`.

`pyproject.toml`:

```toml
[project]
name = "local-agent-stack"
version = "0.1.0"
description = "Local OpenClaw + NemoClaw + A2A + LangGraph-capable agent runtime"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pyyaml>=6.0.2",
  "httpx>=0.27.0",
  "sqlalchemy>=2.0.0",
  "aiosqlite>=0.20.0",
  "python-dotenv>=1.0.1"
]

[project.optional-dependencies]
langgraph = [
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0"
]
postgres = [
  "psycopg[binary,pool]>=3.2.0",
  "langgraph-checkpoint-postgres>=2.0.0"
]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "ruff>=0.6.0",
  "mypy>=1.10.0"
]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Commands:

```bash
uv sync --extra dev
uv run pytest
```

With LangGraph and Postgres:

```bash
uv sync --extra dev --extra langgraph --extra postgres
```

---

## 4. Environment Configuration

`.env.example`:

```env
HOST=127.0.0.1
PORT=8080
ALLOW_DEV_NO_AUTH=true
LOCAL_AGENT_TOKEN=change-me

APP_DATABASE_URL=sqlite:///./data/agent.db

USE_LANGGRAPH=false
LANGGRAPH_CHECKPOINTER=sqlite
LANGGRAPH_SQLITE_PATH=./data/langgraph.db
LANGGRAPH_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/agent_runtime?sslmode=disable

OPENCLAW_ENABLED=false
NEMOCLAW_ENABLED=false
```

Rules:

- Never commit real `.env`.
- Never put bearer tokens, API keys, SSH keys, OAuth refresh tokens, or service account JSON in `agents.yaml`, `AGENTS.md`, Agent Cards, tests, or docs.
- Bind to `127.0.0.1` by default.

---

## 5. `agents.yaml`: Canonical Source of Truth

Create `agents.yaml` with explicit runtime routing.

```yaml
version: 1

runtime:
  default_host: 127.0.0.1
  default_port: 8080
  default_base_url: http://127.0.0.1:8080
  default_a2a_prefix: /a2a
  generated_card_paths:
    - .well-known/agent-card.json
    - .well-known/agent.json

agents:
  bibliography:
    id: bibliography
    name: local-bibliography-agent
    display_name: Local Bibliography Agent
    version: 0.1.0
    description: >
      Extracts bibliographies, resolves scholarly metadata, and finds legally
      available open-access PDFs using public scholarly APIs.

    owner:
      organization: local-dev
      contact: local

    runtime:
      kind: openclaw
      openclaw_agent_id: bibliography
      sandbox: nemoclaw
      graph:
        enabled: true
        module: local_agent_stack.agents.bibliography_agent.graph
        factory: build_graph
        state_schema: local_agent_stack.agents.bibliography_agent.state.BibliographyState
      fallback_graph:
        module: local_agent_stack.agents.generic_agent.graph
        factory: build_graph

    server:
      base_url: http://127.0.0.1:8080
      a2a_endpoint: /a2a/bibliography
      card_paths:
        - /.well-known/agent-card.json
        - /.well-known/agent.json

    auth:
      mode: local_bearer
      env_token_name: LOCAL_AGENT_TOKEN
      allow_none_for_dev: true

    capabilities:
      streaming: true
      push_notifications: false
      state_transition_history: true
      file_upload: true
      artifacts: true

    skills:
      - id: extract-bibliography
        name: Extract Bibliography
        description: Extract bibliography entries from PDF, BibTeX, RIS, or Markdown.
        tags: [research, bibliography, bibtex, pdf]
        input_modes: [text/plain, application/pdf, text/markdown]
        output_modes: [application/json, text/markdown]

      - id: resolve-open-access-pdfs
        name: Resolve Open Access PDFs
        description: Resolve legal open-access PDFs using arXiv, Unpaywall, OpenAlex, and Crossref metadata.
        tags: [open-access, pdf, scholarly-metadata]
        input_modes: [application/json, text/plain]
        output_modes: [application/json]

      - id: summarize-paper
        name: Summarize Paper
        description: Summarize a paper with citation, abstract, claims, method, and limitations.
        tags: [summary, paper, research]
        input_modes: [application/pdf, text/plain]
        output_modes: [text/markdown, application/json]

    behavior:
      instruction_file: src/local_agent_stack/agents/bibliography_agent/AGENTS.md
      generated_root_instruction_file: AGENTS.md
      rules:
        - Never download copyrighted PDFs from unauthorized mirrors.
        - Prefer official publisher pages, arXiv, institutional repositories, and Unpaywall.
        - Keep an audit log of external URLs accessed.
        - Ask for confirmation before deleting files.
        - Store intermediate metadata in data/metadata.jsonl.

    mcp:
      enabled: true
      servers:
        - name: local-filesystem-safe
          command: python
          args: ["-m", "local_agent_stack.tools.filesystem_safe"]

    policy:
      filesystem:
        allowed_roots:
          - ./data
          - ./artifacts
        deny_patterns:
          - ~/.ssh
          - ~/.aws
          - ~/.config/gcloud
      network:
        allow_domains:
          - api.crossref.org
          - api.openalex.org
          - api.semanticscholar.org
          - api.unpaywall.org
          - arxiv.org
          - export.arxiv.org
```

Implementation rules:

- `agents.yaml` is the single source of truth for static metadata.
- `agents.yaml` points to each agent graph module.
- `agents.yaml` may contain policy metadata but not secrets.
- Generate Agent Cards and root `AGENTS.md` from it.
- Per-agent `AGENTS.md` files may be curated manually but should reference `agents.yaml` as the source of registry truth.

---

## 6. Generated Root `AGENTS.md`

Generate root `AGENTS.md` from `agents.yaml`.

Example output:

```md
# AGENTS.md

Generated from `agents.yaml`. Prefer editing `agents.yaml` for registry metadata.

## Local Agent Stack

This repository implements a shared local agent runtime using:

- A2A for agent discovery and invocation.
- OpenClaw for local agent/MCP interaction.
- NemoClaw for sandboxed execution.
- Optional LangGraph for stateful workflow execution.

## Registered Agents

### local-bibliography-agent

Purpose: Extracts bibliographies, resolves scholarly metadata, and finds legally available open-access PDFs.

A2A endpoint:

- `http://127.0.0.1:8080/a2a/bibliography`

Agent Card:

- `http://127.0.0.1:8080/.well-known/agent-card.json`
- `http://127.0.0.1:8080/.well-known/agent.json`

Operating rules:

- Never download copyrighted PDFs from unauthorized mirrors.
- Prefer official publisher pages, arXiv, institutional repositories, and Unpaywall.
- Keep an audit log of external URLs accessed.
- Ask for confirmation before deleting files.
```

---

## 7. A2A Agent Card Generation

Generate:

```text
.well-known/agent-card.json
.well-known/agent.json
```

Use identical JSON at both paths initially.

Expected generated JSON:

```json
{
  "name": "local-bibliography-agent",
  "description": "Extracts bibliographies, resolves scholarly metadata, and finds legally available open-access PDFs using public scholarly APIs.",
  "version": "0.1.0",
  "url": "http://127.0.0.1:8080/a2a/bibliography",
  "provider": {
    "organization": "local-dev"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "authentication": {
    "schemes": ["bearer"]
  },
  "skills": [
    {
      "id": "extract-bibliography",
      "name": "Extract Bibliography",
      "description": "Extract bibliography entries from PDF, BibTeX, RIS, or Markdown.",
      "tags": ["research", "bibliography", "bibtex", "pdf"]
    }
  ]
}
```

Rules:

- Keep Agent Cards stable and minimal.
- Do not expose internal filesystem policy unless necessary.
- Do not expose secrets.
- Validate card shape in tests.
- Multi-agent later can use one well-known aggregate card or per-agent paths. For v0.1, start with one primary agent card.

---

## 8. Shared Runtime: Required Components

### 8.1 `main.py`

`src/local_agent_stack/main.py` should only wire the app.

```python
from fastapi import FastAPI
from local_agent_stack.registry.config import load_config
from local_agent_stack.runtime.a2a_server import router as a2a_router

config = load_config()
app = FastAPI(title="Local Agent Stack")
app.state.config = config
app.include_router(a2a_router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
```

### 8.2 `runtime/a2a_server.py`

Responsibilities:

- Serve Agent Card paths.
- Accept A2A POST requests.
- Extract `agent_id` from path or default agent.
- Authenticate request.
- Create/lookup conversation/task IDs.
- Call `graph_runner.run_agent_task(...)`.
- Return A2A-like JSON-RPC response.

Routes:

```text
GET  /.well-known/agent-card.json
GET  /.well-known/agent.json
POST /a2a/{agent_id}
POST /a2a                  # optional default agent alias
```

Supported methods for v0.1:

```text
agent/card
skills/list
message/send
```

### 8.3 `runtime/graph_runner.py`

Responsibilities:

- Load agent config from registry.
- Dynamically import `module` and `factory` from `agents.yaml`.
- Build or cache compiled graphs.
- Construct `thread_id`.
- Invoke LangGraph if enabled.
- Fallback to generic direct execution when LangGraph is disabled.
- Write audit events before and after execution.

Thread ID convention:

```text
thread_id = {tenant_id}:{agent_id}:{a2a_task_id_or_conversation_id}
```

For local dev:

```text
local:bibliography:<conversation_id>
```

### 8.4 `runtime/checkpointer.py`

Responsibilities:

- Return appropriate LangGraph checkpointer.
- Support no-op/in-memory for tests.
- Support SQLite for local dev if implemented.
- Support Postgres for production.

Pseudo-interface:

```python
def get_checkpointer(settings):
    if not settings.use_langgraph:
        return None
    if settings.langgraph_checkpointer == "postgres":
        return make_postgres_checkpointer(settings.langgraph_postgres_dsn)
    if settings.langgraph_checkpointer == "sqlite":
        return make_sqlite_checkpointer(settings.langgraph_sqlite_path)
    raise ValueError("Unsupported checkpointer")
```

### 8.5 `runtime/storage.py`

Owns app tables, separate from LangGraph checkpoint tables.

Required tables:

```sql
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  agent_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  input_json TEXT,
  output_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  status TEXT NOT NULL,
  request_json TEXT,
  response_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  path TEXT NOT NULL,
  mime_type TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  agent_id TEXT NOT NULL,
  conversation_id TEXT,
  event_type TEXT NOT NULL,
  event_json TEXT,
  created_at TEXT NOT NULL
);
```

### 8.6 `runtime/openclaw_bridge.py`

Responsibilities:

- Shell out to OpenClaw only when `OPENCLAW_ENABLED=true`.
- Provide clear errors when OpenClaw is missing.
- Keep integration loose for v0.1.

Do not assume private OpenClaw config paths.

### 8.7 `runtime/mcp_bridge.py`

Responsibilities:

- Provide a stable internal abstraction for MCP calls.
- For v0.1, allow mocked/local tools.
- Later integrate with OpenClaw MCP server list/config.

### 8.8 `runtime/security.py`

Rules:

- Dev mode may allow unauthenticated localhost calls only when `ALLOW_DEV_NO_AUTH=true`.
- Non-dev requires `Authorization: Bearer <LOCAL_AGENT_TOKEN>`.
- Never log bearer tokens.
- Default bind address is `127.0.0.1`.

---

## 9. Per-Agent Module Contract

Each non-trivial agent should have this shape:

```text
src/local_agent_stack/agents/<agent_name>/
  AGENTS.md
  state.py
  graph.py
  prompts.py
  tools.py
```

### 9.1 `state.py`

Example:

```python
from typing import NotRequired, TypedDict

class BibliographyState(TypedDict):
    tenant_id: str
    agent_id: str
    conversation_id: str
    a2a_task_id: str
    user_message: str
    selected_skill: NotRequired[str]
    input_files: list[str]
    extracted_references: list[dict]
    resolved_metadata: list[dict]
    oa_pdf_candidates: list[dict]
    approved_downloads: list[str]
    tool_calls: list[dict]
    intermediate_results: list[dict]
    approval_required: bool
    final_response: NotRequired[str]
    error: NotRequired[str]
```

### 9.2 `graph.py`

Contract:

```python
def build_graph(config, runtime_services):
    """Return a compiled or uncompiled LangGraph graph for this agent."""
```

The shared `graph_runner` should compile with the shared checkpointer.

Suggested node flow:

```text
receive
→ classify_skill
→ validate_inputs
→ run_domain_tool
→ maybe_request_approval
→ produce_response
→ audit_result
```

### 9.3 `tools.py`

Domain-specific functions only.

Good:

```text
extract_bibliography()
resolve_open_access_pdf_candidates()
summarize_paper()
```

Do not put generic A2A/auth/checkpoint/OpenClaw logic here.

---

## 10. LangGraph Implementation Guidance

### 10.1 When to use LangGraph

Use LangGraph when the agent needs:

- multi-step stateful workflow
- resumability after failure
- human approval pause/resume
- intermediate artifact state
- replay/time-travel debugging
- long-running task state

Do not use LangGraph just to store a plain chat log. Use app DB tables for that.

### 10.2 Feature flag

```env
USE_LANGGRAPH=false
```

When false:

```text
A2A request → direct handler → app DB log → response
```

When true:

```text
A2A request → graph_runner → LangGraph graph → checkpointer → app DB audit → response
```

### 10.3 Postgres checkpointer target

Implement Postgres support behind this setting:

```env
USE_LANGGRAPH=true
LANGGRAPH_CHECKPOINTER=postgres
LANGGRAPH_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/agent_runtime?sslmode=disable
```

Minimal pattern:

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(dsn) as checkpointer:
    checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)
    result = graph.invoke(
        input_state,
        config={"configurable": {"thread_id": thread_id}},
    )
```

Implementation note:

- Avoid calling `setup()` on every request in production.
- Use `scripts/db_init.py` for schema setup.
- Keep LangGraph checkpoint tables separate from app audit tables.

### 10.4 Human approval pattern

For risky actions, use LangGraph interrupt/resume later.

Risky actions:

- deleting files
- sending emails
- committing/pushing code
- calling paid APIs
- downloading bulk PDFs
- modifying tenant/customer data

v0.1 can stub approvals with app DB rows. Full interrupt/resume can be phase 2.

---

## 11. A2A Handling Strategy

Start with a minimal A2A-like JSON-RPC handler. Do not overbuild full protocol support in v0.1.

Example `message/send` request:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "conversation_id": "conv-local-001",
    "message": {
      "role": "user",
      "content": "Extract bibliography from this PDF path: ./data/paper.pdf"
    }
  }
}
```

Example response:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "conversation_id": "conv-local-001",
    "role": "agent",
    "content": "Received. The bibliography extraction workflow has started.",
    "artifacts": []
  }
}
```

Handler behavior:

```text
agent/card
→ return generated Agent Card

skills/list
→ return skills from agents.yaml

message/send
→ authenticate
→ persist incoming message
→ construct task context
→ route to graph_runner
→ persist outgoing message
→ return result
```

---

## 12. OpenClaw Integration

OpenClaw role:

```text
- local agent shell
- MCP/tool management
- operator interface
- optional bridge for running configured local agents
```

Implementation tasks:

1. Add `docs/openclaw.md`.
2. Add `scripts/openclaw_check.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

command -v openclaw >/dev/null 2>&1 || {
  echo "openclaw CLI not found"
  exit 1
}

openclaw --help >/dev/null
openclaw mcp list || true
```

3. Implement `OpenClawBridge`:

```python
class OpenClawBridge:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    async def invoke_agent(self, agent_id: str, message: str) -> dict:
        if not self.enabled:
            return {"status": "disabled", "message": "OpenClaw bridge disabled"}
        # Conservative shell-out placeholder. Do not assume exact CLI args until verified locally.
        raise NotImplementedError("Verify local OpenClaw CLI invocation before enabling")
```

4. Keep disabled by default.

Recommended first milestone:

```text
A2A server works independently.
OpenClaw check script works separately.
OpenClaw bridge is present but disabled by default.
```

---

## 13. NemoClaw Integration

NemoClaw role:

```text
- sandbox containment
- credential boundary
- network/filesystem policy wrapper
- safer execution of local always-on agents
```

Implementation tasks:

1. Add `docs/nemoclaw.md`.
2. Add `scripts/run_in_nemoclaw.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

command -v nemoclaw >/dev/null 2>&1 || {
  echo "nemoclaw CLI not found. Install/configure NemoClaw first."
  exit 1
}

# Exact invocation may vary by installed NemoClaw version.
# Keep this conservative until verified locally.
nemoclaw --help
```

3. Document intended execution:

```text
NemoClaw/OpenShell starts sandbox
→ runs local-agent-stack FastAPI server
→ optionally launches OpenClaw/MCP tooling inside same controlled boundary
```

4. Do not bake secrets into NemoClaw scripts.

---

## 14. Artifact Generator

Create `scripts/generate_agent_artifacts.py`.

It should:

1. Read `agents.yaml`.
2. Validate required fields.
3. Generate root `AGENTS.md`.
4. Generate `.well-known/agent-card.json`.
5. Generate `.well-known/agent.json`.
6. Avoid writing secrets.

Command:

```bash
uv run python scripts/generate_agent_artifacts.py
```

Expected output:

```text
Generated AGENTS.md
Generated .well-known/agent-card.json
Generated .well-known/agent.json
```

---

## 15. Validation Script

Create `scripts/validate_agent_card.py`.

Validate:

- JSON parses.
- `name` exists.
- `description` exists.
- `url` exists.
- `skills` is non-empty.
- each skill has `id`, `name`, and `description`.
- no secret-looking fields exist.

Secret-looking keys to reject:

```text
token
secret
password
api_key
private_key
refresh_token
client_secret
service_account
```

Command:

```bash
uv run python scripts/validate_agent_card.py .well-known/agent-card.json
```

---

## 16. Database Initialization

Create `scripts/db_init.py`.

Responsibilities:

- Create app DB tables.
- If `USE_LANGGRAPH=true` and `LANGGRAPH_CHECKPOINTER=postgres`, initialize LangGraph Postgres checkpoint tables.
- Do not run destructive migrations.

Commands:

```bash
uv run python scripts/db_init.py
```

For local Postgres:

```bash
createdb agent_runtime
USE_LANGGRAPH=true LANGGRAPH_CHECKPOINTER=postgres uv run python scripts/db_init.py
```

---

## 17. Implementation Phases for Cursor

### Phase 1: Scaffold

Tasks:

- Create repo structure.
- Add `pyproject.toml`.
- Add `.env.example`.
- Add initial `agents.yaml`.
- Add minimal FastAPI app.
- Add config loader and schemas.
- Add tests.

Acceptance:

```bash
uv sync --extra dev
uv run pytest
uv run uvicorn local_agent_stack.main:app --host 127.0.0.1 --port 8080
curl http://127.0.0.1:8080/healthz
```

### Phase 2: Artifact Generation

Tasks:

- Implement Agent Card generator.
- Implement root `AGENTS.md` generator.
- Implement validation script.
- Add tests.

Acceptance:

```bash
uv run python scripts/generate_agent_artifacts.py
uv run python scripts/validate_agent_card.py .well-known/agent-card.json
curl http://127.0.0.1:8080/.well-known/agent-card.json | jq
curl http://127.0.0.1:8080/.well-known/agent.json | jq
```

### Phase 3: Shared A2A Runtime

Tasks:

- Implement `runtime/a2a_server.py`.
- Support `agent/card`, `skills/list`, `message/send`.
- Add auth middleware.
- Persist messages.
- Add audit events.

Acceptance:

```bash
curl -s -X POST http://127.0.0.1:8080/a2a/bibliography \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"skills/list","params":{}}' | jq
```

### Phase 4: Per-Agent Graph Contract

Tasks:

- Add `agents/generic_agent`.
- Add `agents/bibliography_agent`.
- Implement `state.py`, `graph.py`, `tools.py` stubs.
- Implement dynamic module loading from `agents.yaml`.

Acceptance:

```bash
uv run pytest tests/test_graph_runner.py
```

### Phase 5: Optional LangGraph

Tasks:

- Add LangGraph dependencies behind extras.
- Implement graph runner feature flag.
- Implement checkpointer factory.
- Support local no-op/direct mode when disabled.
- Support Postgres checkpointer when enabled.

Acceptance:

```bash
uv sync --extra dev --extra langgraph --extra postgres
USE_LANGGRAPH=true LANGGRAPH_CHECKPOINTER=postgres uv run pytest
```

### Phase 6: OpenClaw Bridge

Tasks:

- Add OpenClaw docs.
- Add `openclaw_check.sh`.
- Add disabled-by-default `OpenClawBridge`.
- Add config field mapping from `agents.yaml`.

Acceptance:

```bash
bash scripts/openclaw_check.sh
```

### Phase 7: NemoClaw Wrapper

Tasks:

- Add NemoClaw docs.
- Add `run_in_nemoclaw.sh`.
- Document expected sandbox execution model.
- Keep command conservative until local CLI is verified.

Acceptance:

```bash
bash scripts/run_in_nemoclaw.sh
```

The script may stop after showing help if exact runtime invocation needs local verification.

---

## 18. Cursor Agent Prompt

Paste this into Cursor:

```text
Implement the local-agent-stack project from these instructions.

Main architecture:
- Build a shared runtime, not separate runtimes per agent.
- Use agents.yaml as the canonical registry/config source.
- Generate root AGENTS.md and A2A Agent Card files from agents.yaml.
- Implement per-agent modules with state.py, graph.py, tools.py, prompts.py.
- Keep A2A/auth/storage/LangGraph/OpenClaw/NemoClaw plumbing in shared runtime modules.

Required v0.1 endpoints:
- GET /healthz
- GET /.well-known/agent-card.json
- GET /.well-known/agent.json
- POST /a2a/{agent_id}
- Optional POST /a2a as default-agent alias

Required A2A-like methods:
- agent/card
- skills/list
- message/send

Storage:
- Add normal app tables for conversations, messages, tool_calls, approvals, artifacts, audit_events.
- Do not rely only on LangGraph checkpoints for audit/reporting.
- Add optional LangGraph support behind USE_LANGGRAPH=false by default.
- Add Postgres checkpointer support behind LANGGRAPH_CHECKPOINTER=postgres.

Agent registry:
- agents.yaml must point to each agent graph module and factory.
- A2A Agent Card must not expose secrets or internal unsafe paths.
- AGENTS.md contains behavioral instructions, not secrets.

OpenClaw/NemoClaw:
- Add docs and check/wrapper scripts.
- Keep OpenClaw bridge disabled by default.
- Keep NemoClaw invocation conservative until local CLI details are verified.
- Do not assume private config paths or exact CLI arguments beyond help/checks.

Security:
- Bind to 127.0.0.1 by default.
- Allow unauthenticated local dev only when ALLOW_DEV_NO_AUTH=true.
- Require bearer token otherwise.
- Never log tokens.
- Never commit secrets.

Testing:
- Add tests for agents.yaml loading.
- Add tests for Agent Card generation.
- Add tests for AGENTS.md generation.
- Add tests for A2A discovery endpoints.
- Add tests for skills/list and message/send.
- Add tests for graph runner disabled and enabled paths where practical.

Keep implementation conservative and working. Do not overbuild full A2A protocol support in v0.1. Implement minimal JSON-RPC-like behavior first, with clean interfaces for later replacement.
```

---

## 19. Bottom Line

The tightened architecture is:

```text
One shared runtime
+ many per-agent graph modules
+ agents.yaml registry
+ generated AGENTS.md
+ generated A2A card
+ optional LangGraph execution/checkpointing
+ app DB audit tables
+ OpenClaw bridge
+ NemoClaw sandbox wrapper
```

This avoids duplication and keeps the project maintainable.
