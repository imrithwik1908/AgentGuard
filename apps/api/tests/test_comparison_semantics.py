import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

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

    from agentguard_api.db import session as db_session

    await db_session.engine.dispose()

    from agentguard_api.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _create_project_versions_and_case(client: httpx.AsyncClient) -> dict:
    slug = f"comparison-agent-{uuid.uuid4().hex[:8]}"
    project_response = await client.post(
        "/api/v1/projects",
        json={"name": "Comparison Agent", "slug": slug},
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    baseline_response = await client.post(
        f"/api/v1/projects/{slug}/versions",
        json={"name": "Production", "version": "prod-v1"},
    )
    candidate_response = await client.post(
        f"/api/v1/projects/{slug}/versions",
        json={"name": "Candidate", "version": "candidate-v2"},
    )
    assert baseline_response.status_code == 201, baseline_response.text
    assert candidate_response.status_code == 201, candidate_response.text

    dataset_response = await client.post(
        "/api/v1/datasets",
        json={
            "project_id": project["id"],
            "name": "Policy Regression Suite",
            "slug": f"policy-suite-{uuid.uuid4().hex[:8]}",
            "cases": [
                {
                    "name": "opened-laptop-after-45-days",
                    "input": {"question": "Can I return an opened laptop after 45 days?"},
                    "expected_substring": "opened electronics must be returned within 30 days",
                    "metadata": {"critical": True},
                }
            ],
        },
    )
    assert dataset_response.status_code == 201, dataset_response.text
    return {
        "slug": slug,
        "project": project,
        "baseline": baseline_response.json(),
        "candidate": candidate_response.json(),
        "dataset": dataset_response.json(),
        "case": dataset_response.json()["cases"][0],
    }


async def _trace_for_case(
    client: httpx.AsyncClient,
    *,
    project_slug: str,
    version: str,
    dataset_case_id: str,
    answer: str,
) -> dict:
    response = await client.post(
        "/api/v1/traces",
        json={
            "project_slug": project_slug,
            "version": version,
            "external_trace_id": f"trace-{uuid.uuid4()}",
            "name": "answer-policy-question",
            "status": "OK",
            "input": {
                "question": "Can I return an opened laptop after 45 days?",
                "dataset_case_id": dataset_case_id,
            },
            "output": {"answer": answer},
            "metadata": {"dataset_case_id": dataset_case_id},
            "started_at": _iso(0),
            "ended_at": _iso(100),
            "spans": [
                {
                    "external_span_id": "generate",
                    "type": "LLM",
                    "name": "generate answer",
                    "status": "OK",
                    "started_at": _iso(10),
                    "ended_at": _iso(90),
                    "output": {"answer": answer},
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _evaluation(
    client: httpx.AsyncClient,
    *,
    trace_id: str,
    dataset_id: str,
    dataset_case_id: str,
    score: str,
    passed: bool,
    label: str,
    evaluator_name: str = "builtin.answer_contains",
) -> dict:
    response = await client.post(
        "/api/v1/evaluations",
        json={
            "trace_id": trace_id,
            "dataset_id": dataset_id,
            "dataset_case_id": dataset_case_id,
            "evaluator_name": evaluator_name,
            "score": score,
            "threshold": "1.0000",
            "passed": passed,
            "label": label,
            "explanation": label,
            "metadata": {
                "expected_substring": "opened electronics must be returned within 30 days"
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_historical_results_do_not_corrupt_latest_paired_comparison(api_client):
    stack = await _create_project_versions_and_case(api_client)
    case_id = stack["case"]["id"]
    dataset_id = stack["dataset"]["id"]

    older_baseline = await _trace_for_case(
        api_client,
        project_slug=stack["slug"],
        version="prod-v1",
        dataset_case_id=case_id,
        answer="Opened electronics must be returned within 30 days.",
    )
    await _evaluation(
        api_client,
        trace_id=older_baseline["id"],
        dataset_id=dataset_id,
        dataset_case_id=case_id,
        score="1.0000",
        passed=True,
        label="Historical passing baseline",
    )

    latest_baseline = await _trace_for_case(
        api_client,
        project_slug=stack["slug"],
        version="prod-v1",
        dataset_case_id=case_id,
        answer="Returns are handled by support.",
    )
    await _evaluation(
        api_client,
        trace_id=latest_baseline["id"],
        dataset_id=dataset_id,
        dataset_case_id=case_id,
        score="0.0000",
        passed=False,
        label="Latest failing baseline",
    )

    candidate = await _trace_for_case(
        api_client,
        project_slug=stack["slug"],
        version="candidate-v2",
        dataset_case_id=case_id,
        answer="Returns are handled by support.",
    )
    await _evaluation(
        api_client,
        trace_id=candidate["id"],
        dataset_id=dataset_id,
        dataset_case_id=case_id,
        score="0.0000",
        passed=False,
        label="Candidate equivalent failure",
    )

    response = await api_client.get(
        "/api/v1/evaluations/compare/paired",
        params={
            "baseline_version_id": stack["baseline"]["id"],
            "candidate_version_id": stack["candidate"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    paired = response.json()
    assert paired["regressed"] == []
    assert len(paired["unchanged"]) == 1
    assert paired["unchanged"][0]["baseline_status"] == "FAIL"
    assert paired["unchanged"][0]["candidate_status"] == "FAIL"
    assert paired["comparison_coverage"] == "1.0000"
    assert paired["comparable_case_count"] == 1
    assert paired["total_case_count"] == 1


@pytest.mark.anyio
async def test_pass_fail_and_fail_pass_semantics(api_client):
    stack = await _create_project_versions_and_case(api_client)
    case_id = stack["case"]["id"]
    dataset_id = stack["dataset"]["id"]

    baseline = await _trace_for_case(
        api_client,
        project_slug=stack["slug"],
        version="prod-v1",
        dataset_case_id=case_id,
        answer="Opened electronics must be returned within 30 days.",
    )
    candidate = await _trace_for_case(
        api_client,
        project_slug=stack["slug"],
        version="candidate-v2",
        dataset_case_id=case_id,
        answer="Returns are handled by support.",
    )
    await _evaluation(
        api_client,
        trace_id=baseline["id"],
        dataset_id=dataset_id,
        dataset_case_id=case_id,
        score="1.0000",
        passed=True,
        label="Baseline passed",
    )
    await _evaluation(
        api_client,
        trace_id=candidate["id"],
        dataset_id=dataset_id,
        dataset_case_id=case_id,
        score="0.0000",
        passed=False,
        label="Candidate failed",
    )

    response = await api_client.get(
        "/api/v1/evaluations/compare/paired",
        params={
            "baseline_version_id": stack["baseline"]["id"],
            "candidate_version_id": stack["candidate"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["regressed"]) == 1

    inverse_stack = await _create_project_versions_and_case(api_client)
    inverse_case_id = inverse_stack["case"]["id"]
    inverse_dataset_id = inverse_stack["dataset"]["id"]
    inverse_baseline = await _trace_for_case(
        api_client,
        project_slug=inverse_stack["slug"],
        version="prod-v1",
        dataset_case_id=inverse_case_id,
        answer="Returns are handled by support.",
    )
    inverse_candidate = await _trace_for_case(
        api_client,
        project_slug=inverse_stack["slug"],
        version="candidate-v2",
        dataset_case_id=inverse_case_id,
        answer="Opened electronics must be returned within 30 days.",
    )
    await _evaluation(
        api_client,
        trace_id=inverse_baseline["id"],
        dataset_id=inverse_dataset_id,
        dataset_case_id=inverse_case_id,
        score="0.0000",
        passed=False,
        label="Baseline failed",
    )
    await _evaluation(
        api_client,
        trace_id=inverse_candidate["id"],
        dataset_id=inverse_dataset_id,
        dataset_case_id=inverse_case_id,
        score="1.0000",
        passed=True,
        label="Candidate passed",
    )
    inverse_response = await api_client.get(
        "/api/v1/evaluations/compare/paired",
        params={
            "baseline_version_id": inverse_stack["baseline"]["id"],
            "candidate_version_id": inverse_stack["candidate"]["id"],
        },
    )
    assert inverse_response.status_code == 200, inverse_response.text
    assert len(inverse_response.json()["improved"]) == 1


@pytest.mark.anyio
async def test_release_policy_requires_evidence_and_blocks_runtime_and_critical_failures(
    api_client,
):
    evidence_stack = await _create_project_versions_and_case(api_client)
    evidence_case_id = evidence_stack["case"]["id"]
    evidence_dataset_id = evidence_stack["dataset"]["id"]
    for version_key, version_name in (("baseline", "prod-v1"), ("candidate", "candidate-v2")):
        trace = await _trace_for_case(
            api_client,
            project_slug=evidence_stack["slug"],
            version=version_name,
            dataset_case_id=evidence_case_id,
            answer="Opened electronics must be returned within 30 days.",
        )
        await _evaluation(
            api_client,
            trace_id=trace["id"],
            dataset_id=evidence_dataset_id,
            dataset_case_id=evidence_case_id,
            score="1.0000",
            passed=True,
            label=f"{version_key} answer passed",
        )

    missing_evidence = await api_client.get(
        "/api/v1/evaluations/release-decision",
        params={
            "baseline_version_id": evidence_stack["baseline"]["id"],
            "candidate_version_id": evidence_stack["candidate"]["id"],
            "minimum_pass_rate": "0",
            "allowed_score_drop": "1",
            "required_evaluator": "builtin.runtime_success",
        },
    )
    assert missing_evidence.status_code == 200, missing_evidence.text
    assert missing_evidence.json()["decision"] == "REVIEW"
    assert any(
        "Required evaluator evidence is missing" in reason
        for reason in missing_evidence.json()["reasons"]
    )

    blocker_stack = await _create_project_versions_and_case(api_client)
    blocker_case_id = blocker_stack["case"]["id"]
    blocker_dataset_id = blocker_stack["dataset"]["id"]
    baseline_trace = await _trace_for_case(
        api_client,
        project_slug=blocker_stack["slug"],
        version="prod-v1",
        dataset_case_id=blocker_case_id,
        answer="Opened electronics must be returned within 30 days.",
    )
    candidate_trace = await _trace_for_case(
        api_client,
        project_slug=blocker_stack["slug"],
        version="candidate-v2",
        dataset_case_id=blocker_case_id,
        answer="Returns are handled by support.",
    )
    for trace, passed, score, label in (
        (baseline_trace, True, "1.0000", "baseline passed"),
        (candidate_trace, False, "0.0000", "candidate failed"),
    ):
        await _evaluation(
            api_client,
            trace_id=trace["id"],
            dataset_id=blocker_dataset_id,
            dataset_case_id=blocker_case_id,
            score=score,
            passed=passed,
            label=label,
        )
        await _evaluation(
            api_client,
            trace_id=trace["id"],
            dataset_id=blocker_dataset_id,
            dataset_case_id=blocker_case_id,
            score=score,
            passed=passed,
            label=f"runtime {label}",
            evaluator_name="builtin.runtime_success",
        )

    blocked = await api_client.get(
        "/api/v1/evaluations/release-decision",
        params={
            "baseline_version_id": blocker_stack["baseline"]["id"],
            "candidate_version_id": blocker_stack["candidate"]["id"],
            "minimum_pass_rate": "0",
            "maximum_regressions": "10",
            "allowed_score_drop": "1",
            "required_evaluator": "builtin.runtime_success",
        },
    )
    assert blocked.status_code == 200, blocked.text
    decision = blocked.json()
    assert decision["decision"] == "BLOCK"
    assert decision["runtime_failure_count"] == 1
    assert decision["critical_regression_count"] == 1
    assert any("runtime-success" in reason for reason in decision["reasons"])
    assert any("critical test case" in reason for reason in decision["reasons"])
