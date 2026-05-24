# 12 — Extension Cookbook

Recipes for the most common extension tasks. Each recipe is a small, sequential checklist with the final acceptance command.

These recipes intentionally reach across multiple architecture docs — when in doubt, follow the cross-references in each step.

---

## Recipe A — Add a new workflow

**Goal:** compose existing capabilities into a new workflow, no Python.

1. Edit [`workflows.yaml`](../../workflows.yaml). Add a key under `workflows:`:

   ```yaml
   workflows:
     my_new_workflow:
       version: 0.1.0
       name: My New Workflow
       description: Short description.
       exposed_as_skill:
         id: my-new-skill
         tags: [example]
       inputs:
         query: { type: string, required: true }
       steps:
         - id: search
           call: mcp.fetch.get_json
           with: { url: "https://example.com/search?q={{ inputs.query }}" }
           output: hits
         - id: summarize
           call: agent.bibliography.summarize-paper
           with: { references: "{{ steps.search.hits }}" }
           output: summary
       output:
         summary: "{{ steps.summarize.summary }}"
   ```

2. Validate:

   ```bash
   uv run python scripts/validate_workflows.py workflows.yaml
   ```

3. Regenerate artifacts so the new skill appears on the agent card:

   ```bash
   uv run python scripts/generate_agent_artifacts.py
   ```

4. Restart (or `POST /admin/reload`), then call it:

   ```bash
   curl -s -X POST http://127.0.0.1:8080/a2a/workflows \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer dev-token' \
     -d '{
       "jsonrpc":"2.0","id":"1",
       "method":"message/send",
       "params":{"skill":"my-new-skill","inputs":{"query":"agents"}}
     }' | jq
   ```

References: [03-workflows](03-workflows.md), [05-a2a §3.6](05-a2a.md#36-workflows-as-skills-routing).

---

## Recipe B — Add a new MCP server

**Goal:** make a new MCP server's tools available as `mcp.<server>.<tool>` capabilities.

1. Edit [`mcp_servers.yaml`](../../mcp_servers.yaml). Append under `servers:`:

   ```yaml
   servers:
     my-tool:
       id: my-tool
       transport: stdio
       command: python
       args: ["-m", "agent_stack.tools.my_tool"]
       env_passthrough: [PATH]
       autostart: true
       health: { ready_timeout_seconds: 10 }
       capabilities_filter:
         allow_tools: ["do_thing"]
       policy:
         max_concurrent_calls: 2
         per_call_timeout_seconds: 15
   ```

2. (If stdio) implement the server module under `src/agent_stack/tools/`. Follow the MCP server framework conventions for `tools/list` + `tools/call`.

3. Reload:

   ```bash
   curl -X POST http://127.0.0.1:8080/admin/reload
   ```

4. Verify the capability appeared:

   ```bash
   curl -s http://127.0.0.1:8080/admin/capabilities \
     | jq '.[] | select(.uri | startswith("mcp.my-tool"))'
   ```

5. Use it from any workflow step:

   ```yaml
   - id: example
     call: mcp.my-tool.do_thing
     with: { input: "..." }
   ```

References: [04-mcp-integration](04-mcp-integration.md), [08-security-and-policy §3.6](08-security-and-policy.md#36-per-capability-allowdeny).

---

## Recipe C — Add a new local agent

**Goal:** create a domain-specific agent with one or more skills.

1. Scaffold the module:

   ```
   src/agent_stack/agents/my_agent/
     __init__.py
     AGENTS.md          # behavioral instructions
     state.py           # TypedDict
     graph.py           # build_graph(config, services) -> CompiledGraph
     prompts.py
     tools.py
   ```

2. Edit [`agents.yaml`](../../agents.yaml). Add the agent:

   ```yaml
   agents:
     my_agent:
       id: my_agent
       name: local-my-agent
       version: 0.1.0
       description: ...
       runtime:
         kind: local
         module: agent_stack.agents.my_agent.graph
         factory: build_graph
         state_schema: agent_stack.agents.my_agent.state.MyState
       server:
         base_url: http://127.0.0.1:8080
         a2a_endpoint: /a2a/my_agent
       auth:
         mode: local_bearer
         env_token_name: LOCAL_AGENT_TOKEN
         allow_none_for_dev: true
       skills:
         - id: do-it
           name: Do It
           description: ...
           tags: [example]
   ```

3. Regenerate artifacts and reload:

   ```bash
   uv run python scripts/generate_agent_artifacts.py
   curl -X POST http://127.0.0.1:8080/admin/reload
   ```

4. Smoke test:

   ```bash
   curl -s -X POST http://127.0.0.1:8080/a2a/my_agent \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer dev-token' \
     -d '{"jsonrpc":"2.0","id":"1","method":"skills/list","params":{}}' | jq
   ```

5. Reference the skill from a workflow as `agent.my_agent.do-it`.

References: [01-config-and-registries §3.1](01-config-and-registries.md#31-agentsyaml), [03-workflows](03-workflows.md).

---

## Recipe D — Expose a workflow as an A2A skill

**Goal:** make an existing workflow externally callable.

1. Add `exposed_as_skill` to the workflow entry:

   ```yaml
   exposed_as_skill:
     id: my-skill
     tags: [example]
     input_modes: [text/plain]
     output_modes: [application/json]
   ```

2. Regenerate artifacts so the skill appears under the synthetic `workflows` agent in `.well-known/agent-card.json`:

   ```bash
   uv run python scripts/generate_agent_artifacts.py
   uv run python scripts/validate_agent_card.py .well-known/agent-card.json
   ```

3. Reload and call it via `/a2a/workflows`:

   ```bash
   curl -s -X POST http://127.0.0.1:8080/a2a/workflows \
     -H 'Authorization: Bearer dev-token' \
     -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"skill":"my-skill","inputs":{...}}}' | jq
   ```

References: [05-a2a §3.4](05-a2a.md#34-card-generation-rules), [05-a2a §3.6](05-a2a.md#36-workflows-as-skills-routing).

---

## Recipe E — Call a remote A2A agent from a workflow

**Goal:** call an agent on another host as if it were local.

1. Register the remote in [`agents.yaml`](../../agents.yaml):

   ```yaml
   agents:
     partner_agent:
       id: partner_agent
       runtime:
         kind: remote
         remote:
           base_url: https://partner.example.com
           a2a_endpoint: /a2a/partner
           auth: { mode: bearer, token_env: PARTNER_AGENT_TOKEN }
           resilience:
             connect_timeout_seconds: 5
             read_timeout_seconds: 30
             retry: { max_attempts: 3, backoff_seconds: 1.0, jitter: true }
             circuit_breaker: { failure_threshold: 5, reset_seconds: 30 }
       skills:
         - id: partner-search
           name: Partner Search
           description: ...
           tags: [external]
   ```

2. Put `PARTNER_AGENT_TOKEN=...` in `.env` (never in YAML).

3. Add a workflow step:

   ```yaml
   - id: call_partner
     call: agent.partner_agent.partner-search
     with: { query: "{{ inputs.q }}" }
     timeout_seconds: 15
     retry: { max_attempts: 2, backoff_seconds: 1.0 }
     output: partner_hits
   ```

4. Watch the breaker:

   ```bash
   curl -s http://127.0.0.1:8080/admin/remotes | jq
   ```

References: [01-config-and-registries §3.1](01-config-and-registries.md#31-agentsyaml), [05-a2a §3.5](05-a2a.md#35-outbound-client-a2a_client).

---

## Recipe F — Add a built-in step kind (advanced)

This is a **closed-set extension** and requires updating the architecture doc.

1. Add a Pydantic variant to `runtime/workflows/schema.py`'s step union.
2. Implement the handler in `runtime/workflows/steps.py`.
3. Teach `runtime/workflows/compiler.py` to translate the new kind into a LangGraph node (and edges if it's control-flow).
4. Update [03-workflows §3.3](03-workflows.md#33-step-kinds-closed-set) with the new kind, full grammar, example, and state transitions.
5. Add tests in `tests/unit/test_workflow_compiler.py`.

Acceptance: `uv run pytest tests/unit/test_workflow_compiler.py` is green and the new kind has a worked example in the architecture doc.

References: [03-workflows](03-workflows.md), [06-runtime-and-langgraph](06-runtime-and-langgraph.md).

---

## Recipe G — Add a custom policy

**Goal:** enforce organization-specific rules at the single capability seam.

1. Implement `Policy` in `src/agent_stack/runtime/policy_custom.py`:

   ```python
   class Policy:
       def evaluate(self, call, ctx):
           if call.uri.startswith("mcp.fetch.") and "example.com" not in call.inputs.get("url", ""):
               return Deny(reason="only example.com fetches allowed")
           return Allow()
   ```

2. Wire it in `runtime/capabilities.py` (constructor takes a `Policy` instance; default is `DefaultPolicy`).

3. Update [08-security-and-policy §3.5](08-security-and-policy.md#35-policy-hook) — the *interface* is fixed; your overrides go below the default stack and cannot relax it.

4. Test in `tests/unit/test_capability_policy.py`.

References: [02-capabilities §3.8](02-capabilities.md#38-policy-hook-signature), [08-security-and-policy](08-security-and-policy.md).

---

## Recipe H — Add a new audit event or metric

**Goal:** observe a new operation without bypassing the standard primitives.

1. Decide if you need a **new event type** or a **new metric**. (Often both.)
2. Add the event to [11-observability §3.4](11-observability.md#34-audit-event-taxonomy-closed-set) and to `tests/unit/test_audit_taxonomy.py`.
3. Add the metric to [11-observability §3.3](11-observability.md#33-metric-catalog).
4. Emit from the appropriate module — **never** bypass `capabilities.invoke` for the underlying call.

Acceptance: `uv run pytest tests/unit/test_audit_taxonomy.py` is green and the new metric appears at `/metrics`.

References: [11-observability](11-observability.md), [07-storage-and-audit](07-storage-and-audit.md).

---

## Recipe I — Bump a registry schema version

**Goal:** evolve `agents.yaml`, `workflows.yaml`, or `mcp_servers.yaml` safely.

1. Add the new field(s) to the Pydantic schema in `src/agent_stack/registry/schemas.py`, defaulting to the old behavior where possible.
2. If the change is breaking, bump `schema_version`.
3. Add a migration script: `scripts/migrate_<file>_<from>_to_<to>.py`.
4. Update the migration table in [01-config-and-registries §7](01-config-and-registries.md#7-schema-versioning-and-migrations).
5. Add a test in `tests/unit/test_<file>_yaml.py` that loads a fixture at the new version.

Acceptance: `uv run pytest tests/unit/` is green; CI fails any PR that bumps a `schema_version` without a migration script (enforced by `tests/test_docs_snippets.py` companion).

References: [01-config-and-registries §7](01-config-and-registries.md#7-schema-versioning-and-migrations).

---

## Anti-recipes (don't do these)

- **Don't** bypass `capabilities.invoke` to call MCP / a sub-workflow / a remote agent directly from an agent's `tools.py`. You'll skip policy, audit, and tracing.
- **Don't** put secret values in any YAML or in `AGENTS.md`. Use env var **names**.
- **Don't** query LangGraph checkpoint tables from app code. Query `audit_events` / `tool_calls` instead.
- **Don't** add a new step kind without updating [03-workflows §3.3](03-workflows.md#33-step-kinds-closed-set) — the closed set is part of the contract.
- **Don't** rename an existing `event_type` or `error_code`. They're stable. Add new ones; deprecate old ones in a separate cycle.

---

## Cross-references

- [00-overview](00-overview.md) — where each thing fits.
- [02-capabilities](02-capabilities.md) — invocation envelope.
- [03-workflows](03-workflows.md) — workflow grammar.
- [04-mcp-integration](04-mcp-integration.md) — MCP bridge details.
- [05-a2a](05-a2a.md) — A2A surfaces.
- [08-security-and-policy](08-security-and-policy.md) — secret and policy rules.
- [11-observability](11-observability.md) — logs/spans/metrics/audit.
