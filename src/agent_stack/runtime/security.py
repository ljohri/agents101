"""Inbound auth helpers."""

from __future__ import annotations

import hmac
import ipaddress

from fastapi import HTTPException, Request

from agent_stack.settings import Settings


def _client_host(request: Request) -> str:
    if request.client is None:
        return ""
    return request.client.host


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in {"localhost", "::1", "testclient"}


def require_auth(request: Request, settings: Settings, token_env_name: str = "LOCAL_AGENT_TOKEN") -> None:
    host = _client_host(request)
    auth = request.headers.get("Authorization", "")
    if settings.allow_dev_no_auth and _is_loopback(host) and not auth:
        return
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    supplied = auth.removeprefix("Bearer ").strip()
    expected = settings.local_agent_token
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")


def require_localhost(request: Request) -> None:
    if not _is_loopback(_client_host(request)):
        raise HTTPException(status_code=404, detail="not found")
