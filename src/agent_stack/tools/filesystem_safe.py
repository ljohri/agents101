"""In-process MCP tool implementations (v0.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path("./data").resolve()
ARTIFACTS = Path("./artifacts").resolve()


def _safe_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    for root in (ROOT, ARTIFACTS):
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(f"path outside allowed roots: {path}")


async def read_file(path: str) -> dict[str, Any]:
    p = _safe_path(path)
    return {"path": str(p), "content": p.read_text(encoding="utf-8")}


async def write_file(path: str, content: str) -> dict[str, Any]:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": str(p), "bytes": len(content.encode())}


async def download_url(url: str, dest: str) -> dict[str, Any]:
    p = _safe_path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    # v0.1 stub: record intent without network fetch in tests
    p.write_text(f"stub-download:{url}\n", encoding="utf-8")
    return {"url": url, "dest": str(p), "status": "stubbed"}


TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "download_url": download_url,
}
