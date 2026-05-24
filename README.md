# agents101 — Workflow-Driven Local Agent Stack

A local, file-driven agent runtime where **MCP tools**, **A2A agent skills**, and **declarative workflows** are unified under a single capability model. The headline goal: any combination of MCP tools and agent skills can be composed into a new workflow via [`workflows.yaml`](workflows.yaml) — no Python required for the common case.

## Where to start

- **Build plan (canonical):** [`docs/build-plan.md`](docs/build-plan.md)
- **Architecture docs:** [`docs/architecture/`](docs/architecture/) (start with [`00-overview.md`](docs/architecture/00-overview.md))
- **Legacy plan (superseded):** [`docs/legacy/openclaw_nemoclaw_a2a_cursor_implementation.md`](docs/legacy/openclaw_nemoclaw_a2a_cursor_implementation.md)

## Core ideas

- **Capability URI** is the single addressing scheme:
  - `mcp.<server>.<tool>` — an MCP tool exposed by a configured server
  - `agent.<agent_id>.<skill_id>` — a local or remote A2A agent skill
  - `workflow.<workflow_id>` — a compiled declarative workflow
  - `builtin.<name>` — runtime built-ins (`branch`, `parallel`, `for_each`, `human_approval`, `assign`, `emit_artifact`)
- **One invocation seam:** `capabilities.invoke(uri, inputs, ctx)` applies auth, policy, audit, and tracing uniformly.
- **Workflows compile to LangGraph** at boot; sub-workflow calls work via the same checkpointer.
- **Workflows become A2A skills** — they're externally callable and composable by other agents.

## Layout (planned)

```
agents101/
  agents.yaml          # local + remote agents
  workflows.yaml       # declarative workflows
  mcp_servers.yaml     # MCP server registry
  AGENTS.md            # generated
  .well-known/         # generated agent cards
  src/agent_stack/     # runtime, registry, agents, tools
  scripts/             # generators, validators, db_init
  docs/                # build plan + architecture docs
  tests/               # unit / integration / contract / security / golden / chaos
```

See the [build plan](docs/build-plan.md) for the phased implementation.
