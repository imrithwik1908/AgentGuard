import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("AGENTGUARD_TEST_DATABASE_URL"),
    reason="AGENTGUARD_TEST_DATABASE_URL is required for Postgres integration tests",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _iso(offset_ms: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(milliseconds=offset_ms)).isoformat()


@pytest.fixture
async def auth_client(monkeypatch):
    from agentguard_api.core.config import get_settings

    monkeypatch.setenv("AGENTGUARD_DATABASE_URL", os.environ["AGENTGUARD_TEST_DATABASE_URL"])
    monkeypatch.setenv("AGENTGUARD_AUTH_REQUIRED", "true")
    monkeypatch.setenv("AGENTGUARD_ACCESS_TOKEN_MINUTES", "60")
    get_settings.cache_clear()

    from agentguard_api.db import session as db_session

    await db_session.engine.dispose()

    from agentguard_api.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _register(client: httpx.AsyncClient, label: str) -> dict:
    response = await client.post(
        "/api/v1/security/auth/register",
        json={
            "workspace_name": f"{label} Workspace",
            "workspace_slug": f"{label.lower()}-{uuid.uuid4().hex[:8]}",
            "email": f"{label.lower()}-{uuid.uuid4().hex[:8]}@example.com",
            "name": f"{label} Owner",
            "password": "CorrectHorse123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bearer(tokens: dict) -> dict[str, str]:
    return {"authorization": f"Bearer {tokens['access_token']}"}


async def _create_project_stack(
    client: httpx.AsyncClient,
    tokens: dict,
    *,
    slug: str,
) -> dict:
    project_response = await client.post(
        "/api/v1/projects",
        headers=_bearer(tokens),
        json={"name": f"{slug} Project", "slug": slug},
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    version_response = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=_bearer(tokens),
        json={"name": "Baseline", "version": "v1"},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()

    dataset_response = await client.post(
        "/api/v1/datasets",
        headers=_bearer(tokens),
        json={
            "project_id": project["id"],
            "name": "Regression Suite",
            "slug": f"suite-{uuid.uuid4().hex[:8]}",
            "cases": [
                {
                    "name": "agentguard-definition",
                    "input": {"question": "What is AgentGuard?"},
                    "expected_substring": "captures traces",
                }
            ],
        },
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset = dataset_response.json()

    trace_response = await client.post(
        "/api/v1/traces",
        headers=_bearer(tokens),
        json={
            "project_slug": slug,
            "version": "v1",
            "external_trace_id": f"trace-{uuid.uuid4()}",
            "name": "answer-question",
            "status": "OK",
            "started_at": _iso(0),
            "ended_at": _iso(100),
            "spans": [
                {
                    "external_span_id": "generate",
                    "type": "LLM",
                    "name": "generate",
                    "status": "OK",
                    "started_at": _iso(10),
                    "ended_at": _iso(80),
                }
            ],
        },
    )
    assert trace_response.status_code == 201, trace_response.text
    trace = trace_response.json()

    evaluation_response = await client.post(
        f"/api/v1/evaluations/traces/{trace['id']}/status-check",
        headers=_bearer(tokens),
    )
    assert evaluation_response.status_code == 201, evaluation_response.text
    evaluation = evaluation_response.json()

    return {
        "project": project,
        "version": version,
        "dataset": dataset,
        "case": dataset["cases"][0],
        "trace": trace,
        "evaluation": evaluation,
    }


@pytest.mark.anyio
async def test_auth_lifecycle_and_cross_tenant_api_isolation(auth_client):
    unauthenticated = await auth_client.get("/api/v1/projects")
    assert unauthenticated.status_code == 401

    user_a = await _register(auth_client, "A")
    user_b = await _register(auth_client, "B")

    bad_login = await auth_client.post(
        "/api/v1/security/auth/login",
        json={"email": user_a["user"]["email"], "password": "wrong"},
    )
    assert bad_login.status_code == 401

    login = await auth_client.post(
        "/api/v1/security/auth/login",
        json={
            "email": user_a["user"]["email"],
            "password": "CorrectHorse123",
            "workspace_slug": user_a["workspace"]["slug"],
        },
    )
    assert login.status_code == 200

    stack_a = await _create_project_stack(
        auth_client, user_a, slug=f"a-project-{uuid.uuid4().hex[:8]}"
    )
    stack_b = await _create_project_stack(
        auth_client, user_b, slug=f"b-project-{uuid.uuid4().hex[:8]}"
    )

    list_as_b = await auth_client.get("/api/v1/projects", headers=_bearer(user_b))
    assert list_as_b.status_code == 200
    b_project_ids = {item["id"] for item in list_as_b.json()}
    assert stack_b["project"]["id"] in b_project_ids
    assert stack_a["project"]["id"] not in b_project_ids

    idor_checks = [
        await auth_client.get(
            f"/api/v1/projects/{stack_a['project']['id']}",
            headers=_bearer(user_b),
        ),
        await auth_client.get(
            f"/api/v1/projects/{stack_a['project']['slug']}",
            headers=_bearer(user_b),
        ),
        await auth_client.patch(
            f"/api/v1/projects/{stack_a['project']['id']}",
            headers=_bearer(user_b),
            json={"description": "stolen"},
        ),
        await auth_client.post(
            f"/api/v1/projects/{stack_a['project']['id']}/versions",
            headers=_bearer(user_b),
            json={"name": "Bad", "version": "v2"},
        ),
        await auth_client.get(
            f"/api/v1/datasets/{stack_a['dataset']['id']}",
            headers=_bearer(user_b),
        ),
        await auth_client.get(
            f"/api/v1/datasets/{stack_a['dataset']['id']}/export",
            headers=_bearer(user_b),
        ),
        await auth_client.post(
            f"/api/v1/datasets/{stack_a['dataset']['id']}/cases",
            headers=_bearer(user_b),
            json={
                "name": "foreign-case",
                "input": {"question": "Can I see this?"},
                "expected_substring": "no",
            },
        ),
        await auth_client.post(
            f"/api/v1/datasets/cases/{stack_a['case']['id']}/run",
            headers=_bearer(user_b),
            json={"application_version_id": stack_a["version"]["id"]},
        ),
        await auth_client.get(f"/api/v1/traces/{stack_a['trace']['id']}", headers=_bearer(user_b)),
        await auth_client.post(
            f"/api/v1/evaluations/traces/{stack_a['trace']['id']}/status-check",
            headers=_bearer(user_b),
        ),
        await auth_client.get(
            f"/api/v1/evaluations/summary/{stack_a['version']['id']}",
            headers=_bearer(user_b),
        ),
        await auth_client.get(
            "/api/v1/evaluations/compare",
            headers=_bearer(user_b),
            params={
                "baseline_version_id": stack_a["version"]["id"],
                "candidate_version_id": stack_b["version"]["id"],
            },
        ),
        await auth_client.get(
            "/api/v1/evaluations/release-decision",
            headers=_bearer(user_b),
            params={
                "baseline_version_id": stack_a["version"]["id"],
                "candidate_version_id": stack_b["version"]["id"],
            },
        ),
    ]
    assert {response.status_code for response in idor_checks} <= {403, 404, 422}
    assert all(stack_a["project"]["slug"] not in response.text for response in idor_checks)

    foreign_key = await auth_client.post(
        "/api/v1/security/api-keys",
        headers=_bearer(user_b),
        json={"workspace_id": user_a["workspace"]["id"], "name": "foreign"},
    )
    assert foreign_key.status_code == 403

    key_a_response = await auth_client.post(
        "/api/v1/security/api-keys",
        headers=_bearer(user_a),
        json={"workspace_id": user_a["workspace"]["id"], "name": "sdk"},
    )
    assert key_a_response.status_code == 201
    key_b_response = await auth_client.post(
        "/api/v1/security/api-keys",
        headers=_bearer(user_b),
        json={"workspace_id": user_b["workspace"]["id"], "name": "sdk"},
    )
    assert key_b_response.status_code == 201

    foreign_ingest = await auth_client.post(
        "/api/v1/traces",
        headers={"x-agentguard-api-key": key_b_response.json()["api_key"]},
        json={
            "project_slug": stack_a["project"]["slug"],
            "version": "v1",
            "external_trace_id": f"foreign-{uuid.uuid4()}",
            "name": "foreign",
            "status": "OK",
            "started_at": _iso(0),
            "ended_at": _iso(10),
            "spans": [],
        },
    )
    assert foreign_ingest.status_code == 404
    assert stack_a["project"]["slug"] not in foreign_ingest.text

    allowed_ingest = await auth_client.post(
        "/api/v1/traces",
        headers={"x-agentguard-api-key": key_a_response.json()["api_key"]},
        json={
            "project_slug": stack_a["project"]["slug"],
            "version": "v1",
            "external_trace_id": f"allowed-{uuid.uuid4()}",
            "name": "allowed",
            "status": "OK",
            "started_at": _iso(0),
            "ended_at": _iso(10),
            "spans": [],
        },
    )
    assert allowed_ingest.status_code == 201

    refreshed = await auth_client.post(
        "/api/v1/security/auth/refresh",
        json={"refresh_token": user_a["refresh_token"]},
    )
    assert refreshed.status_code == 200
    refreshed_tokens = refreshed.json()

    logout = await auth_client.post(
        "/api/v1/security/auth/logout",
        headers=_bearer(refreshed_tokens),
    )
    assert logout.status_code == 204
    after_logout = await auth_client.get("/api/v1/projects", headers=_bearer(refreshed_tokens))
    assert after_logout.status_code == 401

    token_hash = hashlib.sha256(user_b["access_token"].encode("utf-8")).hexdigest()
    engine = create_async_engine(os.environ["AGENTGUARD_TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.execute(
            text("update auth_sessions set expires_at = now() - interval '1 minute' "
                 "where access_token_hash = :token_hash"),
            {"token_hash": token_hash},
        )
    await engine.dispose()

    expired = await auth_client.get("/api/v1/projects", headers=_bearer(user_b))
    assert expired.status_code == 401
