"""Integration tests for A2A endpoints."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from agent_stack.main import create_app
from tests.conftest import REPO_ROOT


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(str(REPO_ROOT)))


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["config_loaded"] is True


def test_agent_card(client: TestClient) -> None:
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "skills" in data


def test_skills_list_bibliography(client: TestClient) -> None:
    r = client.post(
        "/a2a/bibliography",
        json={"jsonrpc": "2.0", "id": "1", "method": "skills/list", "params": {}},
    )
    assert r.status_code == 200
    skills = r.json()["result"]["skills"]
    assert any(s["id"] == "extract-bibliography" for s in skills)


def test_message_send_echo(client: TestClient) -> None:
    r = client.post(
        "/a2a/generic",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {"skill": "echo", "inputs": {"message": "hello"}},
        },
    )
    assert r.status_code == 200
    body = r.json()["result"]["content"]
    assert "hello" in body


def test_workflow_bibliography_research(client: TestClient) -> None:
    r = client.post(
        "/a2a/workflows",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "skill": "bibliography-research",
                "inputs": {"pdf_path": "./data/paper.pdf"},
            },
        },
    )
    assert r.status_code == 200
    content = json.loads(r.json()["result"]["content"])
    assert "references" in content or "result" in content
