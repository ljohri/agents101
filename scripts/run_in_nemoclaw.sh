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
