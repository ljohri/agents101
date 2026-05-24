# Architecture documentation

Read in order, or jump to what you need.

| # | Doc | Topic |
|---|-----|-------|
| 00 | [overview](00-overview.md) | layer cake, design principles, request lifecycle |
| 01 | [config and registries](01-config-and-registries.md) | `agents.yaml`, `workflows.yaml`, `mcp_servers.yaml` |
| 02 | [capabilities](02-capabilities.md) | URI scheme, registry, invocation envelope, error model |
| 03 | [workflows](03-workflows.md) | YAML grammar, step kinds, expressions, compilation |
| 04 | [MCP integration](04-mcp-integration.md) | bridge lifecycle, transports, discovery, schema cache |
| 05 | [A2A](05-a2a.md) | server + outbound client, multi-agent, workflows-as-skills |
| 06 | [runtime and LangGraph](06-runtime-and-langgraph.md) | graph runner, checkpointer, interrupts |
| 07 | [storage and audit](07-storage-and-audit.md) | app tables vs. checkpoints, DDL, retention |
| 08 | [security and policy](08-security-and-policy.md) | auth, allow/deny, secrets, per-capability policy |
| 09 | [OpenClaw](09-openclaw.md) | role, bridge, disabled-by-default posture |
| 10 | [NemoClaw](10-nemoclaw.md) | sandbox model |
| 11 | [observability](11-observability.md) | logs, OTEL spans, metrics, audit-event taxonomy |
| 12 | [extension cookbook](12-extension-cookbook.md) | recipes for adding workflows, MCP servers, agents |

All docs follow the same outline (Purpose · Concepts · Contract · Diagrams · Failure modes · Extension points · Worked example · Cross-references), except the cookbook which is recipe-based.

Every fenced block tagged with `file=<path>` is asserted equal to the real file by `tests/test_docs_snippets.py` — docs cannot drift silently.
