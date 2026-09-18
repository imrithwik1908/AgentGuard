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
async def api_client(monkeypatch):
    from agentguard_api.core.config import get_settings

    monkeypatch.setenv("AGENTGUARD_DATABASE_URL", os.environ["AGENTGUARD_TEST_DATABASE_URL"])
    get_settings.cache_clear()

    from agentguard_api.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.anyio
async def test_trace_ingestion_api_checkpoint_behaviors(api_client):
    slug = f"research-agent-{uuid.uuid4().hex[:8]}"
    project_response = await api_client.post(
        "/api/v1/projects",
        json={"name": "Research Agent", "slug": slug},
    )
    assert project_response.status_code == 201

    workspace_response = await api_client.post(
        "/api/v1/security/workspaces",
        json={"name": "Interview Workspace", "slug": f"workspace-{uuid.uuid4().hex[:8]}"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    user_response = await api_client.post(
        "/api/v1/security/users",
        json={
            "workspace_id": workspace["id"],
            "email": "owner@example.com",
            "name": "Owner",
            "role": "owner",
        },
    )
    assert user_response.status_code == 201
    key_response = await api_client.post(
        "/api/v1/security/api-keys",
        json={"workspace_id": workspace["id"], "name": "CI"},
    )
    assert key_response.status_code == 201
    assert key_response.json()["api_key"].startswith("ag_")
    provider_response = await api_client.post(
        "/api/v1/security/providers",
        json={
            "workspace_id": workspace["id"],
            "provider": "openai",
            "name": "Production OpenAI",
            "default_model": "gpt-4.1-mini",
            "api_key_secret_ref": "AGENTGUARD_OPENAI_API_KEY",
        },
    )
    assert provider_response.status_code == 201
    redaction_response = await api_client.post(
        "/api/v1/security/redaction-policies",
        json={
            "workspace_id": workspace["id"],
            "name": "emails",
            "patterns": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        },
    )
    assert redaction_response.status_code == 201

    version_response = await api_client.post(
        f"/api/v1/projects/{slug}/versions",
        json={"name": "Initial local version", "version": "v1"},
    )
    assert version_response.status_code == 201

    external_trace_id = f"trace-{uuid.uuid4()}"
    trace_payload = {
        "project_slug": slug,
        "version": "v1",
        "external_trace_id": external_trace_id,
        "name": "answer-question",
        "status": "OK",
        "started_at": _iso(0),
        "ended_at": _iso(1000),
        "spans": [
            {
                "external_span_id": "retrieve",
                "type": "RETRIEVER",
                "name": "retrieve",
                "status": "OK",
                "started_at": _iso(10),
                "ended_at": _iso(100),
            },
            {
                "external_span_id": "tool",
                "parent_external_span_id": "retrieve",
                "type": "TOOL",
                "name": "summarize",
                "status": "OK",
                "started_at": _iso(20),
                "ended_at": _iso(80),
            },
        ],
    }

    ingest_response = await api_client.post("/api/v1/traces", json=trace_payload)
    assert ingest_response.status_code == 201
    stored = ingest_response.json()
    assert stored["duration_ms"] >= 900
    assert stored["spans"][1]["parent_span_id"] == stored["spans"][0]["id"]

    duplicate_response = await api_client.post("/api/v1/traces", json=trace_payload)
    assert duplicate_response.status_code == 409

    evaluation_response = await api_client.post(
        f"/api/v1/evaluations/traces/{stored['id']}/status-check"
    )
    assert evaluation_response.status_code == 201
    evaluation = evaluation_response.json()
    assert evaluation["evaluator_name"] == "builtin.trace_status"
    assert evaluation["score"] == "1.0000"
    assert evaluation["status"] == "PASS"
    assert evaluation["passed"] is True

    duplicate_evaluation_response = await api_client.post(
        f"/api/v1/evaluations/traces/{stored['id']}/status-check"
    )
    assert duplicate_evaluation_response.status_code == 409

    summary_response = await api_client.get(
        f"/api/v1/evaluations/summary/{stored['application_version_id']}"
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["evaluation_count"] == 1
    assert summary["pass_count"] == 1
    assert summary["average_score"] == "1.0000"

    v2_response = await api_client.post(
        f"/api/v1/projects/{slug}/versions",
        json={"name": "Regression candidate", "version": "v2"},
    )
    assert v2_response.status_code == 201

    failed_trace_payload = trace_payload | {
        "version": "v2",
        "external_trace_id": f"trace-failed-{uuid.uuid4()}",
        "status": "ERROR",
        "error": {"type": "RuntimeError", "message": "candidate failed"},
    }
    failed_trace_response = await api_client.post("/api/v1/traces", json=failed_trace_payload)
    assert failed_trace_response.status_code == 201
    failed_trace = failed_trace_response.json()
    failed_evaluation_response = await api_client.post(
        f"/api/v1/evaluations/traces/{failed_trace['id']}/status-check"
    )
    assert failed_evaluation_response.status_code == 201
    assert failed_evaluation_response.json()["status"] == "FAIL"

    comparison_response = await api_client.get(
        "/api/v1/evaluations/compare",
        params={
            "baseline_version_id": stored["application_version_id"],
            "candidate_version_id": failed_trace["application_version_id"],
        },
    )
    assert comparison_response.status_code == 200
    comparison = comparison_response.json()
    assert comparison["score_delta"] == "-1.0000"
    assert comparison["pass_rate_delta"] == "-1.0000"
    assert comparison["regression_count_delta"] == 1

    release_response = await api_client.get(
        "/api/v1/evaluations/release-decision",
        params={
            "baseline_version_id": stored["application_version_id"],
            "candidate_version_id": failed_trace["application_version_id"],
            "minimum_pass_rate": "0.8000",
            "maximum_regressions": 0,
            "allowed_score_drop": "0.0000",
        },
    )
    assert release_response.status_code == 200
    release = release_response.json()
    assert release["decision"] == "REVIEW"
    assert release["comparison"]["regression_count_delta"] == 1
    assert any("No behavioral test cases" in reason for reason in release["reasons"])

    ci_response = await api_client.get(
        "/api/v1/ci/release-gate",
        params={
            "baseline_version_id": stored["application_version_id"],
            "candidate_version_id": failed_trace["application_version_id"],
        },
    )
    assert ci_response.status_code == 200
    assert ci_response.json()["passed"] is False
    assert ci_response.json()["exit_code"] == 1

    dataset_response = await api_client.post(
        "/api/v1/datasets",
        json={
            "project_id": project_response.json()["id"],
            "name": "Demo Agent Golden Set",
            "slug": f"demo-agent-golden-{uuid.uuid4().hex[:8]}",
            "description": "Small deterministic dataset for answer quality checks.",
            "cases": [
                {
                    "name": "explains-agentguard",
                    "input": {"question": "What is AgentGuard?"},
                    "expected_substring": "captures traces",
                },
                {
                    "name": "missing-expectation",
                    "input": {"question": "What is AgentGuard?"},
                    "expected_substring": "this phrase will not appear",
                },
            ],
        },
    )
    assert dataset_response.status_code == 201
    dataset = dataset_response.json()
    assert len(dataset["cases"]) == 2

    export_response = await api_client.get(f"/api/v1/datasets/{dataset['id']}/export")
    assert export_response.status_code == 200
    imported = export_response.json() | {
        "slug": f"imported-{uuid.uuid4().hex[:8]}",
        "project_id": project_response.json()["id"],
    }
    import_response = await api_client.post("/api/v1/datasets/import", json=imported)
    assert import_response.status_code == 201
    assert len(import_response.json()["cases"]) == 2

    dataset_list_response = await api_client.get("/api/v1/datasets")
    assert dataset_list_response.status_code == 200
    assert dataset_list_response.json()["total"] >= 1

    passing_case = dataset["cases"][0]
    run_response = await api_client.post(
        f"/api/v1/datasets/cases/{passing_case['id']}/run",
        json={"application_version_id": stored["application_version_id"]},
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["trace"]["name"].startswith("dataset:")
    assert run["trace"]["metadata"]["source"] == "dataset_run"
    assert run["evaluation"]["evaluator_name"] == "builtin.answer_contains"
    assert run["evaluation"]["dataset_case_id"] == passing_case["id"]
    assert run["evaluation"]["status"] == "PASS"

    failing_case = dataset["cases"][1]
    failing_run_response = await api_client.post(
        f"/api/v1/datasets/cases/{failing_case['id']}/run",
        json={"application_version_id": stored["application_version_id"]},
    )
    assert failing_run_response.status_code == 201
    assert failing_run_response.json()["evaluation"]["status"] == "FAIL"

    keyword_run_response = await api_client.post(
        f"/api/v1/datasets/cases/{passing_case['id']}/run",
        json={
            "application_version_id": stored["application_version_id"],
            "evaluator_name": "builtin.keyword_coverage",
        },
    )
    assert keyword_run_response.status_code == 201
    assert keyword_run_response.json()["evaluation"]["evaluator_name"] == "builtin.keyword_coverage"
    assert keyword_run_response.json()["evaluation"]["evaluator_version"] == "1.0.0"
    assert keyword_run_response.json()["evaluation"]["method"] == "DETERMINISTIC_BEHAVIORAL"

    candidate_small_delta_response = await api_client.post(
        "/api/v1/evaluations",
        json={
            "trace_id": failed_trace["id"],
            "dataset_id": dataset["id"],
            "dataset_case_id": passing_case["id"],
            "evaluator_name": "builtin.keyword_coverage",
            "score": "0.9600",
            "threshold": "0.8000",
            "passed": True,
            "label": "Candidate retained keyword coverage",
            "explanation": "Synthetic tiny score movement for tolerance testing.",
            "metadata": {"source": "test"},
        },
    )
    assert candidate_small_delta_response.status_code == 201

    candidate_case_evaluation_response = await api_client.post(
        "/api/v1/evaluations",
        json={
            "trace_id": failed_trace["id"],
            "dataset_id": dataset["id"],
            "dataset_case_id": passing_case["id"],
            "evaluator_name": "builtin.answer_contains",
            "score": "0.0000",
            "threshold": "1.0000",
            "passed": False,
            "label": "Candidate missed required answer content",
            "explanation": "Synthetic paired regression evidence for the same dataset case.",
            "metadata": {"source": "test"},
        },
    )
    assert candidate_case_evaluation_response.status_code == 201

    paired_response = await api_client.get(
        "/api/v1/evaluations/compare/paired",
        params={
            "baseline_version_id": stored["application_version_id"],
            "candidate_version_id": failed_trace["application_version_id"],
        },
    )
    assert paired_response.status_code == 200
    paired = paired_response.json()
    assert len(paired["regressed"]) >= 1
    assert paired["regressed"][0]["classification"] == "REGRESSED"
    assert any(item["evaluator_name"] == "builtin.keyword_coverage" for item in paired["unchanged"])

    paired_release_response = await api_client.get(
        "/api/v1/evaluations/release-decision",
        params={
            "baseline_version_id": stored["application_version_id"],
            "candidate_version_id": failed_trace["application_version_id"],
            "minimum_pass_rate": "0.8000",
            "maximum_regressions": 0,
            "allowed_score_drop": "0.0000",
        },
    )
    assert paired_release_response.status_code == 200
    paired_release = paired_release_response.json()
    assert paired_release["decision"] == "BLOCK"
    assert any("paired regressions" in reason for reason in paired_release["reasons"])

    job_response = await api_client.post(
        "/api/v1/evaluations/jobs",
        json={
            "dataset_id": dataset["id"],
            "application_version_id": stored["application_version_id"],
            "evaluator_name": "builtin.answer_contains",
            "request_id": f"job-{uuid.uuid4()}",
        },
    )
    assert job_response.status_code == 202
    job = job_response.json()
    assert job["status"] in {"QUEUED", "RUNNING", "COMPLETED", "PARTIAL"}
    assert job["total_cases"] == len(dataset["cases"])
    assert job["queue_job_id"] is None

    job_read_response = await api_client.get(f"/api/v1/evaluations/jobs/{job['id']}")
    assert job_read_response.status_code == 200
    assert len(job_read_response.json()["cases"]) == len(dataset["cases"])

    invalid_parent = trace_payload | {
        "external_trace_id": f"invalid-{uuid.uuid4()}",
        "spans": [
            {
                "external_span_id": "child",
                "parent_external_span_id": "missing",
                "type": "TOOL",
                "name": "child",
                "status": "OK",
                "started_at": _iso(10),
                "ended_at": _iso(20),
            }
        ],
    }
    invalid_response = await api_client.post("/api/v1/traces", json=invalid_parent)
    assert invalid_response.status_code == 422

    rollback_id = f"rollback-{uuid.uuid4()}"
    rollback_payload = trace_payload | {
        "external_trace_id": rollback_id,
        "spans": [
            {
                "external_span_id": "child",
                "parent_external_span_id": "parent",
                "type": "TOOL",
                "name": "child",
                "status": "OK",
                "started_at": _iso(20),
                "ended_at": _iso(30),
            },
            {
                "external_span_id": "parent",
                "type": "CHAIN",
                "name": "parent",
                "status": "OK",
                "started_at": _iso(10),
                "ended_at": _iso(40),
            },
        ],
    }
    rollback_response = await api_client.post("/api/v1/traces", json=rollback_payload)
    assert rollback_response.status_code == 422

    engine = create_async_engine(os.environ["AGENTGUARD_TEST_DATABASE_URL"])
    async with engine.connect() as connection:
        trace_count = await connection.scalar(
            text("select count(*) from traces where external_trace_id = :external_trace_id"),
            {"external_trace_id": rollback_id},
        )
        span_count = await connection.scalar(
            text(
                "select count(*) from spans s join traces t on t.id = s.trace_id "
                "where t.external_trace_id = :external_trace_id"
            ),
            {"external_trace_id": rollback_id},
        )
    await engine.dispose()

    assert trace_count == 0
    assert span_count == 0
