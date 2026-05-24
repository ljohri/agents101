#!/usr/bin/env bash
# Copy committed *.yaml.example samples to private local config files (gitignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

copy_if_missing() {
  local src="$1" dst="$2"
  if [[ -f "$dst" ]]; then
    echo "keep existing $dst"
  else
    cp "$src" "$dst"
    echo "created $dst from $src"
  fi
}

copy_if_missing agents.yaml.example agents.yaml
copy_if_missing workflows.yaml.example workflows.yaml
copy_if_missing mcp_servers.yaml.example mcp_servers.yaml

if [[ ! -f .env ]] && [[ -f .env.example ]]; then
  cp .env.example .env
  echo "created .env from .env.example (edit LOCAL_AGENT_TOKEN before production use)"
fi

echo "Local private config ready. Edit agents.yaml / workflows.yaml / mcp_servers.yaml freely — they are not pushed to GitHub."
