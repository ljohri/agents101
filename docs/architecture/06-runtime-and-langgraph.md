# 06 — Runtime and LangGraph

## 1. Purpose

Specify how the **graph runner** drives both per-agent graphs and compiled workflows on top of LangGraph: the control flow, the thread-ID grammar, the checkpointer factory, and the interrupt/resume contract. Also clarify which concerns belong at **compile time** vs. **run time**.

## 2. Concepts

- **Graph runner** (`runtime/graph_runner.py`) — the single entrypoint the A2A server calls. Dispatches to a compiled agent graph or a compiled workflow.
- **Compiled artifact** — either an agent graph (built by the per-agent `build_graph` factory) or a workflow (built by `runtime/workflows/compiler.py`). Both end up as LangGraph `CompiledGraph` instances.
- **Checkpointer** — LangGraph's persistence backend for graph state. Selected by `runtime/checkpointer.py` from env: in-memory, SQLite, or Postgres.
- **Thread ID** — the LangGraph key for a conversation's state lineage. The runtime owns the grammar.
- **Interrupt** — a planned LangGraph pause for human approval. v0.1 implements a *stubbed* form via the `approvals` app table; full LangGraph `interrupt/resume` is deferred.

## 3. Contract

### 3.1 Graph runner control flow

```python
class GraphRunner:
    def __init__(self, registry: Registry, checkpointer: BaseCheckpointer | None):
        ...

    async def run_agent_task(
        self,
        *,
        agent_id: str,
        conversation_id: str,
        message: Message,
        skill: str | None,
        inputs: dict | None,
        ctx: InvocationContext,
    ) -> AgentResponse: ...

    async def run_workflow(
        self,
        *,
        workflow_id: str,
        conversation_id: str,
        inputs: dict,
        ctx: InvocationContext,
    ) -> dict: ...
```

Both methods:

1. Build or fetch the cached compiled artifact.
2. Construct the thread ID (§3.2).
3. Build the initial state (merge prior checkpoint if present).
4. Invoke `graph.ainvoke(state, config={"configurable": {"thread_id": ...}, "callbacks": [...]})`.
5. Persist outgoing message (for agents) or projected output (for workflows).
6. Emit audit events bookending the invocation.

### 3.2 Thread-ID grammar

```
THREAD_ID := AGENT_THREAD | WORKFLOW_THREAD | SUBWORKFLOW_THREAD
AGENT_THREAD       := TENANT ":agent:" AGENT_ID ":" CONVERSATION_ID
WORKFLOW_THREAD    := TENANT ":workflow:" WORKFLOW_ID ":" WORKFLOW_VERSION ":" CONVERSATION_ID
SUBWORKFLOW_THREAD := PARENT_THREAD ":" PARENT_STEP_ID
TENANT             := IDENT          # defaults to "local"
```

Rules:
- Bumping a workflow's `version` field cleanly starts a fresh state lineage instead of mutating old checkpoints.
- Sub-workflow threads include the parent step id to keep multiple invocations distinct.
- Tenant defaults to `local` in v0.1 but the grammar is multi-tenant-ready.

### 3.3 Checkpointer factory

```python
def get_checkpointer(settings: Settings) -> BaseCheckpointer | None:
    if not settings.use_langgraph:
        return None
    match settings.langgraph_checkpointer:
        case "memory":   return MemorySaver()
        case "sqlite":   return make_sqlite_saver(settings.langgraph_sqlite_path)
        case "postgres": return make_postgres_saver(settings.langgraph_postgres_dsn)
        case other:      raise ValueError(f"Unknown checkpointer: {other!r}")
```

Settings:

| Env | Default | Purpose |
|-----|---------|---------|
| `USE_LANGGRAPH` | `false` | Master switch. When false, agents run directly (no checkpointing) and workflows still compile + execute but use `MemorySaver`. |
| `LANGGRAPH_CHECKPOINTER` | `memory` | `memory` \| `sqlite` \| `postgres`. |
| `LANGGRAPH_SQLITE_PATH` | `./data/langgraph.db` | SQLite file. |
| `LANGGRAPH_POSTGRES_DSN` | (none) | Postgres DSN. |

Initialization (`scripts/db_init.py`) creates the Postgres tables once; do **not** call `setup()` on every request.

### 3.4 Interrupt / resume (v0.1 stub, v0.2 native)

- v0.1: a `human_approval` workflow step writes to `approvals`, emits `workflow.approval.requested`, and returns control to the caller with `output={"approval_id": ..., "status": "pending"}`. A separate endpoint (planned: `POST /a2a/{agent_id}` with method `approvals/resolve`) flips the row to `approved`/`denied` and re-runs the workflow, which checkpoints from the prior step.
- v0.2: switch `human_approval` to LangGraph's native `interrupt(...)` and resume from `Command(resume=...)`. No grammar change for `workflows.yaml`.

### 3.5 Per-agent vs. workflow execution

| Concern | Agent graph | Workflow |
|---------|-------------|----------|
| Compiled by | `agents/<name>/graph.build_graph(config, services)` | `runtime/workflows/compiler.compile(workflow_def)` |
| State schema | TypedDict in `state.py` | TypedDict derived from `inputs` + step outputs |
| Cached | yes, per process | yes, per process; rebuilt on hot reload |
| Thread ID | `local:agent:<id>:<conv>` | `local:workflow:<id>:<ver>:<conv>` |
| Calls capabilities? | yes, freely from any node | yes, exclusively (one `capabilities.invoke` per step) |

## 4. Diagrams

### 4.1 Runner dispatch

```mermaid
flowchart TB
    a2a["A2A POST /a2a/AGENT or /a2a/workflows"]
    a2a --> dispatch{kind?}
    dispatch -->|agent| getAgent[graph_runner.run_agent_task]
    dispatch -->|workflow| getWf[graph_runner.run_workflow]
    getAgent --> build1{compiled cached?}
    build1 -->|yes| inv1[graph.ainvoke]
    build1 -->|no| compile1[build_graph factory] --> inv1
    getWf --> build2{compiled cached?}
    build2 -->|yes| inv2[graph.ainvoke]
    build2 -->|no| compile2[workflow compiler] --> inv2
    inv1 --> ckpt1[(checkpointer)]
    inv2 --> ckpt2[(checkpointer)]
```

### 4.2 Resume after approval (v0.1)

```mermaid
sequenceDiagram
    autonumber
    participant Op as Operator
    participant API as POST /a2a/workflows approvals/resolve
    participant DB as approvals table
    participant GR as Graph Runner
    participant WF as Compiled Workflow

    Op->>API: resolve(approval_id, approved)
    API->>DB: update row -> approved
    API->>GR: run_workflow(workflow_id, conversation_id, resume=true)
    GR->>WF: ainvoke with same thread_id
    WF->>WF: checkpoint shows pre-approval state; advance
    WF-->>GR: result
    GR-->>API: response
    API-->>Op: 200 OK
```

## 5. Failure modes

| Symptom | Cause | Behavior |
|---------|-------|----------|
| Workflow ignores prior state on resume | Different `conversation_id` or version bumped | New thread ID → fresh state. Reuse the same conversation_id and don't bump version mid-conversation. |
| LangGraph errors with "checkpointer not configured" | `USE_LANGGRAPH=true` but checkpointer factory returned None | Inspect `LANGGRAPH_CHECKPOINTER`; fall back to `memory`. |
| Postgres `setup()` runs on every boot | Misuse of `PostgresSaver.from_conn_string` per-request | Run `scripts/db_init.py` once; afterwards reuse the saver. |
| Agent graph blocks because a sub-workflow never completed | Sub-workflow's thread orphaned (e.g., crash before commit) | Resume by replaying the parent message; child thread is derived deterministically. |

## 6. Extension points

- **New checkpointer**: implement a `BaseCheckpointer`-compatible class and add a case in `get_checkpointer`.
- **Per-tenant graph caches**: extend the cache key from `(artifact_id, version)` to `(tenant_id, artifact_id, version)`.
- **Custom node tracing**: pass extra LangGraph callbacks from `runtime/observability.py`; never modify the graph definition.
- **Approval channels** beyond the in-band API: implement an external resolver that writes to `approvals` and triggers `run_workflow(..., resume=true)`.

## 7. Worked example — running a workflow with Postgres checkpointing

`.env`:

```env
USE_LANGGRAPH=true
LANGGRAPH_CHECKPOINTER=postgres
LANGGRAPH_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/agent_runtime
```

Boot:

```bash
createdb agent_runtime
USE_LANGGRAPH=true LANGGRAPH_CHECKPOINTER=postgres uv run python scripts/db_init.py
uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8086
```

Run a workflow:

```bash
curl -s -X POST http://127.0.0.1:8086/a2a/workflows \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer dev-token' \
  -d '{
    "jsonrpc":"2.0","id":"1",
    "method":"message/send",
    "params":{
      "conversation_id":"conv-001",
      "skill":"bibliography-research",
      "inputs":{"pdf_path":"./data/paper.pdf"}
    }
  }' | jq
```

The workflow checkpoints after each step. If the process is killed mid-step and restarted with the same `conversation_id`, the next call resumes from the last checkpointed step (provided `version` is unchanged).

## 8. Cross-references

- [02-capabilities](02-capabilities.md) — the envelope every node uses.
- [03-workflows](03-workflows.md) — compilation contract.
- [05-a2a](05-a2a.md) — how the runner is dispatched from inbound requests.
- [07-storage-and-audit](07-storage-and-audit.md) — separation of LangGraph checkpoints vs. app tables.
- [11-observability](11-observability.md) — span/log attributes including `workflow.id`, `workflow.version`, `workflow.step_id`.
