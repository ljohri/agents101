"""Echo tool."""

from __future__ import annotations

from typing import Any


async def echo(message: str) -> dict[str, Any]:
    return {"echo": message}
