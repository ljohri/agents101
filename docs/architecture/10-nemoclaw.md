# 10 — NemoClaw

## 1. Purpose

Specify the runtime's relationship to **NemoClaw** — a sandbox / OpenShell containment / policy boundary. NemoClaw is **disabled by default** and the integration is intentionally conservative: documentation and a wrapper script that prints help, until a local CLI is verified.

## 2. Concepts

- **NemoClaw** — a sandbox/containment layer intended to constrain process, network, and credential boundaries for local always-on agents.
- **OpenShell** — the controlled shell environment NemoClaw provides.
- **Wrapper script** — `scripts/run_in_nemoclaw.sh`. v0.1 only verifies CLI presence and prints help; it does **not** assume an invocation grammar for actually launching the runtime inside the sandbox.

## 3. Contract

### 3.1 Intended execution model (when locally verified)

```
NemoClaw / OpenShell starts sandbox
  → runs the FastAPI server (uvicorn ...) inside the sandbox
  → optionally launches MCP servers inside the same sandbox
  → network egress restricted to allow_domains
  → filesystem writes restricted to data/ and artifacts/
```

### 3.2 What the runtime relies on NemoClaw for (when active)

- **Process containment**: stdio MCP servers spawned by `mcp_bridge` inherit the sandbox.
- **Network restriction**: outbound HTTP/SSE (MCP + A2A client) restricted to `agents.<id>.policy.network.allow_domains` ∪ MCP server URLs.
- **Filesystem restriction**: write access only to `./data/` and `./artifacts/` (and other roots declared in `policy.filesystem.allowed_roots`).
- **Credential isolation**: only env vars explicitly enumerated in launch config reach the sandbox; secrets in `~/.ssh`, `~/.aws`, etc., are *not* visible.

The runtime works correctly without NemoClaw on a developer laptop; sandbox boundaries are an additional layer, not a substitute for the runtime's own policy hooks.

### 3.3 Wrapper script (v0.1)

```bash file=scripts/run_in_nemoclaw.sh
#!/usr/bin/env bash
set -euo pipefail

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw CLI not found. Install/configure NemoClaw, or run the server directly:"
  echo "  uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8080"
  exit 1
fi

# Exact invocation grammar varies by installed NemoClaw version.
# Verify locally before adding a real launch line here.
nemoclaw --help
echo ""
echo "Edit this script with the verified 'nemoclaw run ...' invocation."
```

This is **deliberately incomplete**. It exits 0 after printing help so users can see what's available; it does *not* speculate about the right launch arguments.

### 3.4 What the wrapper does *not* do

- It does not start uvicorn inside the sandbox until the launch grammar is verified locally.
- It does not write or mount any NemoClaw config.
- It does not propagate secrets — env passthrough is configured at the NemoClaw level once verified.

## 4. Diagrams

```mermaid
flowchart TB
    nemo[NemoClaw sandbox]
    subgraph inside [Inside sandbox]
        api[FastAPI A2A server]
        bridge[mcp_bridge supervised stdio servers]
        mcpProc1[(filesystem-safe)]
        mcpProc2[(fetch over http if local)]
    end
    nemo --- inside
    api --> bridge
    bridge --> mcpProc1
    bridge --> mcpProc2
    inside -- network -->|allow_domains only| external[External APIs]
    inside -- fs -->|./data ./artifacts| diskAllowed[Allowed roots]
    inside -. denied .- diskDenied[~/.ssh ~/.aws ...]
```

## 5. Failure modes

| Symptom | Cause | Resolution |
|---------|-------|------------|
| `nemoclaw CLI not found` | Not installed | Run the server directly; install NemoClaw later. |
| Inside-sandbox network calls fail | Domain not on allowlist | Add to `policy.network.allow_domains` *and* (when NemoClaw is active) the sandbox egress rule. |
| Filesystem writes fail with `EACCES` | Path outside `allowed_roots` | Update `policy.filesystem.allowed_roots`. |
| Agent reads secrets it shouldn't have | Sandbox env passthrough too broad | Tighten the sandbox launch's env list. |

## 6. Extension points

- **Verified launch line**: once verified locally, update `scripts/run_in_nemoclaw.sh` with the actual `nemoclaw run ...` invocation.
- **Per-agent sandboxes**: in the future, launch each agent (or each MCP server) in its own sandbox; coordinate via well-known TCP sockets on `127.0.0.1`.
- **CI sandbox testing**: a separate workflow that launches the runtime inside a NemoClaw container and runs the integration suite against it.

## 7. Worked example — current minimal flow

Without NemoClaw (the common path):

```bash
uv run uvicorn agent_stack.main:app --host 127.0.0.1 --port 8080
```

With NemoClaw (after local verification):

```bash
bash scripts/run_in_nemoclaw.sh
# (after editing the script to include the verified 'nemoclaw run' line)
```

## 8. Cross-references

- [09-openclaw](09-openclaw.md) — sibling integration; both are optional.
- [04-mcp-integration](04-mcp-integration.md) — stdio MCP servers run inside the sandbox when active.
- [08-security-and-policy](08-security-and-policy.md) — `policy.filesystem` and `policy.network` blocks the runtime enforces independently.
