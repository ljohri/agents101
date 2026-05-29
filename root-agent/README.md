# root-agent — Root Planner Agent

A standalone process that becomes the single entrypoint in front of the
`agent_stack` runtime. It decides *how* to fulfill a request and delegates to
the existing agents and workflows over **A2A**.

## What it does

1. **LLM-as-judge** — given the catalog of existing workflows (id + description),
   decides whether a deterministic workflow already satisfies the request.
2. **LLM-as-planner** — otherwise reads discovered agent cards + capabilities
   (and available local commands) and synthesizes a plan, then executes it.

Cross-cutting:

- **Memory (Claude-style)** — loads global + local + session memory and injects
  the relevant context into the judge/planner prompts and into the workflow.
- **Global commands** — a registry of CLI recipes describing how to do a task
  with local command-line utilities, exposed as guarded `command.<name>` steps.
- **MCP** — can host its own MCP servers (see `config/mcp_servers.yaml.example`).

## Layout

```
root-agent/
  config/            root_agent.yaml, mcp_servers.yaml.example, commands/
  root_agent/        the package (settings, config, discovery, memory, commands, llm, planner, ...)
```

## Quick start

```bash
cd root-agent
cp .env.example .env          # set LLM_PROVIDER + credentials
uv sync --extra dev           # plus --extra openai|anthropic|vertex as needed
# start the agent_stack runtime first (separate process, port 8086), then:
uv run uvicorn root_agent.main:app --host 127.0.0.1 --port 8443
```

Query it with the CLI utility:

```bash
uv run root-agent agents      # which downstream agents are up/down
uv run root-agent commands    # which local command recipes are available
uv run root-agent ask "find open-access PDFs for ./data/paper.pdf"
```

See [../docs/how-it-fits-together.md](../docs/how-it-fits-together.md) for how
the root agent fits into the overall architecture.
