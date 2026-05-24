#!/usr/bin/env bash
set -euo pipefail

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw CLI not found. Install OpenClaw or unset OPENCLAW_ENABLED."
  exit 1
fi

openclaw --help >/dev/null
echo "openclaw CLI present:"
openclaw --version || true
openclaw mcp list || true
