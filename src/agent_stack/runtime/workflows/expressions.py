"""Sandboxed workflow expression evaluation."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

_EXPR_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def _coalesce(*args: Any) -> Any:
    for a in args:
        if a is not None:
            return a
    return None


def _default(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


def _regex_match(pattern: str, value: str) -> bool:
    return re.search(pattern, str(value)) is not None


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _AttrDict(dict):
    """Dict with attribute access for workflow expressions."""

    def __getattr__(self, item: str):
        try:
            val = self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc
        if isinstance(val, dict):
            return _AttrDict(val)
        return val


def _wrap_scope(scope: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in scope.items():
        out[k] = _AttrDict(v) if isinstance(v, dict) else v
    return out
def _eval_expr(expr: str, scope: dict[str, Any]) -> Any:
    wrapped = _wrap_scope(scope)
    allowed = {
        "len": len,
        "now": _now,
        "uuid": lambda: str(uuid.uuid4()),
        "json": json,
        "default": _default,
        "coalesce": _coalesce,
        "regex_match": _regex_match,
        **wrapped,
    }
    try:
        return eval(expr, {"__builtins__": {}}, allowed)  # noqa: S307 — sandboxed whitelist
    except Exception as exc:
        raise ValueError(f"expression error: {expr!r}: {exc}") from exc


def render_template(template: str, scope: dict[str, Any]) -> Any:
    if "{{" not in template:
        return template
    if template.strip().startswith("{{") and template.strip().endswith("}}"):
        inner = template.strip()[2:-2].strip()
        return _eval_expr(inner, scope)
    out = template
    for match in _EXPR_RE.finditer(template):
        val = _eval_expr(match.group(1), scope)
        out = out.replace(match.group(0), str(val))
    return out


def render_value(value: Any, scope: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return render_template(value, scope)
    if isinstance(value, dict):
        return {k: render_value(v, scope) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(v, scope) for v in value]
    return value
