from __future__ import annotations

import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from agentguard import AgentGuard

API_URL = "http://127.0.0.1:8000"
WEB_URL = "http://localhost:3000"

CORPUS = [
    {
        "id": "returns-standard",
        "title": "Standard Returns",
        "body": (
            "Unopened items can be returned within 30 days. Opened electronics can be returned "
            "within 14 days when accessories and packaging are included."
        ),
    },
    {
        "id": "returns-laptop-exception",
        "title": "Laptop Return Exception",
        "body": (
            "Opened laptops are eligible for refund only within 14 days. After 14 days, support "
            "should offer warranty repair options instead of promising a refund."
        ),
    },
    {
        "id": "holiday-extension",
        "title": "Holiday Extension",
        "body": (
            "Purchases made between November 1 and December 24 can be returned until January 31. "
            "This extension excludes activated subscriptions and final-sale clearance."
        ),
    },
    {
        "id": "final-sale",
        "title": "Final Sale",
        "body": "Final-sale clearance items cannot be returned unless the item arrived defective.",
    },
    {
        "id": "shipping-basic",
        "title": "Shipping Basics",
        "body": "Standard shipping takes 5 to 7 business days. Weekends do not count as business days.",
    },
    {
        "id": "shipping-expedited",
        "title": "Expedited Shipping",
        "body": (
            "Expedited shipping usually takes 2 business days, but weather and carrier disruption "
            "can delay delivery."
        ),
    },
    {
        "id": "warranty",
        "title": "Warranty",
        "body": (
            "Electronics include a one-year limited warranty for manufacturing defects. Accidental "
            "damage is excluded unless the customer bought protection."
        ),
    },
    {
        "id": "price-match",
        "title": "Price Match",
        "body": (
            "A price match can be requested within 7 days when the lower price is from an approved "
            "retailer and the item is identical and in stock."
        ),
    },
    {
        "id": "marketing-laptop-sale",
        "title": "Spring Laptop Sale",
        "body": (
            "Laptop bags and accessories are discounted this spring. This marketing page does not "
            "change return eligibility."
        ),
    },
]

TEST_CASES = [
    {
        "name": "opened laptop after a month",
        "question": "I opened a laptop 32 days ago. Can I still get a refund?",
        "expected": "repair",
        "required_doc": "returns-laptop-exception",
    },
    {
        "name": "holiday return timing",
        "question": "I bought headphones on December 12. Is January 20 still inside the return window?",
        "expected": "January 31",
        "required_doc": "holiday-extension",
    },
    {
        "name": "final sale defective exception",
        "question": "A final-sale item arrived defective. Is any return allowed?",
        "expected": "defective",
        "required_doc": "final-sale",
    },
    {
        "name": "weekend shipping wording",
        "question": "Does standard shipping count Saturday and Sunday?",
        "expected": "Weekends do not count",
        "required_doc": "shipping-basic",
    },
    {
        "name": "expedited weather delay",
        "question": "Can bad weather delay two-day expedited shipping?",
        "expected": "weather",
        "required_doc": "shipping-expedited",
    },
    {
        "name": "price match similar item",
        "question": "Can support price-match a similar but not identical item?",
        "expected": "identical",
        "required_doc": "price-match",
    },
    {
        "name": "warranty accidental damage",
        "question": "Does the one-year electronics warranty cover accidental damage?",
        "expected": "excluded",
        "required_doc": "warranty",
    },
    {
        "name": "holiday activated subscription",
        "question": "Does the holiday return extension refund an activated subscription?",
        "expected": "excludes activated subscriptions",
        "required_doc": "holiday-extension",
    },
    {
        "name": "unopened return window",
        "question": "How long do I have to return an unopened speaker?",
        "expected": "30 days",
        "required_doc": "returns-standard",
    },
    {
        "name": "laptop marketing distractor",
        "question": "The spring laptop sale mentions accessories. Does that change laptop return eligibility?",
        "expected": "does not change",
        "required_doc": "marketing-laptop-sale",
    },
]


@dataclass(frozen=True)
class VersionConfig:
    version: str
    name: str
    top_k: int
    answer_style: str
    retrieval_bias: str


BASELINE = VersionConfig(
    version="baseline-balanced",
    name="Baseline balanced retrieval",
    top_k=3,
    answer_style="careful",
    retrieval_bias="policy",
)
CANDIDATE = VersionConfig(
    version="candidate-broader-context",
    name="Candidate broader context",
    top_k=6,
    answer_style="direct",
    retrieval_bias="recency",
)


def http_json(path: str, *, method: str = "GET", body: Any | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return None if not raw else json.loads(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = raw
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {details}") from exc


def terms(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def retrieve(question: str, config: VersionConfig) -> list[dict[str, Any]]:
    query_terms = terms(question)
    scored: list[tuple[float, dict[str, str]]] = []
    for doc in CORPUS:
        doc_terms = terms(f"{doc['title']} {doc['body']}")
        overlap = len(query_terms & doc_terms)
        score = overlap / max(len(query_terms), 1)
        if config.retrieval_bias == "recency" and doc["id"] in {
            "marketing-laptop-sale",
            "holiday-extension",
        }:
            score += 0.12
        if overlap:
            scored.append((score, doc))
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)[: config.top_k]
    return [
        {"id": doc["id"], "title": doc["title"], "body": doc["body"], "score": round(score, 4)}
        for score, doc in ranked
    ]


def generate_answer(question: str, docs: list[dict[str, Any]], config: VersionConfig) -> str:
    doc_ids = [doc["id"] for doc in docs]
    body = " ".join(doc["body"] for doc in docs)

    if "laptop" in question.lower() and "marketing-laptop-sale" in doc_ids and config.answer_style == "direct":
        return (
            "The sale page says laptop accessories are discounted, but return eligibility still "
            "depends on the return policy. I would check the standard return window."
        )
    if "activated subscription" in question.lower() and "holiday-extension" in doc_ids:
        return "The holiday extension excludes activated subscriptions, so it should not refund one."
    if "final-sale" in question.lower() or "final sale" in question.lower():
        return "Final-sale items cannot be returned unless the item arrived defective."
    if "accidental damage" in question.lower():
        return "Accidental damage is excluded unless the customer bought protection."
    if "price-match" in question.lower() or "price match" in question.lower():
        return "A price match requires an identical item from an approved retailer within 7 days."
    if "weather" in question.lower():
        return "Yes. Weather and carrier disruption can delay expedited shipping."
    if "saturday" in question.lower() or "sunday" in question.lower():
        return "Standard shipping is measured in business days. Weekends do not count."
    if "unopened" in question.lower():
        return "Unopened items can be returned within 30 days."
    if "january" in question.lower() or "december" in question.lower():
        return "Holiday purchases can be returned until January 31 unless an exclusion applies."
    if "laptop" in question.lower() and "32" in question:
        if config.answer_style == "careful":
            return "After 14 days, support should offer warranty repair options instead of a refund."
        return "Opened electronics have a short return window; support should review warranty options."
    return f"Based on the retrieved policies: {body}"


def run_app_case(
    *,
    client: AgentGuard,
    config: VersionConfig,
    case: dict[str, str],
    external_trace_id: str,
) -> dict[str, Any]:
    with client.trace(
        "alice-support-answer",
        input={"question": case["question"]},
        metadata={"case_name": case["name"], "app_owner": "Alice", "version": config.version},
        external_trace_id=external_trace_id,
    ) as trace:
        with trace.span(
            "retrieve support policies",
            type="RETRIEVER",
            input={"question": case["question"], "top_k": config.top_k},
            metadata={"required_doc": case["required_doc"]},
        ) as span:
            docs = retrieve(case["question"], config)
            span.set_output({"documents": docs})

        with trace.span(
            "generate answer",
            type="LLM",
            input={"question": case["question"], "document_ids": [doc["id"] for doc in docs]},
        ) as span:
            answer = generate_answer(case["question"], docs, config)
            span.set_attributes(
                provider="alice-mock-provider",
                model_name="support-mock-2026",
                input_tokens=90 + len(docs) * 40,
                output_tokens=len(answer.split()),
                prompt_style=config.answer_style,
            )
            span.set_output({"answer": answer})

        result = {
            "question": case["question"],
            "answer": answer,
            "retrieved_document_ids": [doc["id"] for doc in docs],
            "expected": case["expected"],
            "required_doc": case["required_doc"],
        }
        trace.set_output(result)
        return result


def find_trace(project_id: str, version_id: str, external_trace_id: str, token: str) -> dict[str, Any]:
    for _ in range(20):
        traces = http_json(
            f"/api/v1/traces?project_id={project_id}&application_version_id={version_id}&limit=100",
            token=token,
        )
        for trace in traces["items"]:
            if trace["external_trace_id"] == external_trace_id:
                return trace
        time.sleep(0.1)
    raise RuntimeError(f"trace {external_trace_id} was not found")


def score_answer(answer: str, expected: str) -> tuple[float, bool]:
    passed = expected.lower() in answer.lower()
    return (1.0 if passed else 0.35, passed)


def main() -> int:
    unique = uuid.uuid4().hex[:8]
    email = f"alice-{unique}@example.com"
    password = "AliceDemo123"
    workspace_slug = f"alice-lab-{unique}"
    project_slug = f"alice-support-agent-{unique}"

    auth = http_json(
        "/api/v1/security/auth/register",
        method="POST",
        body={
            "workspace_name": "Alice Reliability Lab",
            "workspace_slug": workspace_slug,
            "email": email,
            "name": "Alice",
            "password": password,
        },
    )
    token = auth["access_token"]
    workspace_id = auth["workspace"]["id"]

    api_key_payload = http_json(
        "/api/v1/security/api-keys",
        method="POST",
        token=token,
        body={"workspace_id": workspace_id, "name": "Alice local SDK"},
    )
    sdk_key = api_key_payload["api_key"]

    project = http_json(
        "/api/v1/projects",
        method="POST",
        token=token,
        body={
            "name": "Alice Support Agent",
            "slug": project_slug,
            "description": "Alice's realistic support-policy RAG assistant.",
        },
    )

    versions: dict[str, dict[str, Any]] = {}
    for config in [BASELINE, CANDIDATE]:
        versions[config.version] = http_json(
            f"/api/v1/projects/{project['id']}/versions",
            method="POST",
            token=token,
            body={
                "name": config.name,
                "version": config.version,
                "retrieval_config": {"top_k": config.top_k, "bias": config.retrieval_bias},
                "prompt_config": {"answer_style": config.answer_style},
                "model_configuration": {"provider": "mock", "model": "support-mock-2026"},
            },
        )

    dataset = http_json(
        "/api/v1/datasets",
        method="POST",
        token=token,
        body={
            "project_id": project["id"],
            "name": "Alice Support Regression Suite",
            "slug": f"alice-support-suite-{unique}",
            "description": "Natural support-policy cases with distractors and edge cases.",
            "cases": [
                {
                    "name": case["name"],
                    "input": {"question": case["question"]},
                    "expected_substring": case["expected"],
                    "metadata": {"required_doc": case["required_doc"]},
                }
                for case in TEST_CASES
            ],
        },
    )
    cases_by_name = {case["name"]: case for case in dataset["cases"]}

    rows = []
    for config in [BASELINE, CANDIDATE]:
        sdk = AgentGuard(
            base_url=API_URL,
            project=project_slug,
            version=config.version,
            api_key=sdk_key,
            raise_on_failure=True,
        )
        for case in TEST_CASES:
            external_trace_id = f"alice-{config.version}-{case['name'].replace(' ', '-')}-{unique}"
            result = run_app_case(
                client=sdk,
                config=config,
                case=case,
                external_trace_id=external_trace_id,
            )
            version_id = versions[config.version]["id"]
            trace = find_trace(project["id"], version_id, external_trace_id, token)
            answer_score, answer_passed = score_answer(result["answer"], case["expected"])
            retrieval_passed = case["required_doc"] in result["retrieved_document_ids"]
            for evaluator_name, score, passed, label, metadata in [
                (
                    "alice.answer_requirement",
                    answer_score,
                    answer_passed,
                    "Expected answer requirement met"
                    if answer_passed
                    else "Expected answer requirement missed",
                    {"expected": case["expected"], "answer": result["answer"]},
                ),
                (
                    "alice.required_document_retrieved",
                    1.0 if retrieval_passed else 0.0,
                    retrieval_passed,
                    "Required evidence retrieved" if retrieval_passed else "Required evidence missing",
                    {
                        "required_doc": case["required_doc"],
                        "retrieved_document_ids": result["retrieved_document_ids"],
                    },
                ),
            ]:
                http_json(
                    "/api/v1/evaluations",
                    method="POST",
                    token=token,
                    body={
                        "trace_id": trace["id"],
                        "dataset_id": dataset["id"],
                        "dataset_case_id": cases_by_name[case["name"]]["id"],
                        "evaluator_name": evaluator_name,
                        "evaluator_version": "alice-demo-v1",
                        "method": "DETERMINISTIC_BEHAVIORAL",
                        "rubric": {
                            "case_name": case["name"],
                            "meaning": "A lightweight deterministic check for Alice's demo.",
                        },
                        "score": f"{score:.4f}",
                        "threshold": "1.0000",
                        "passed": passed,
                        "label": label,
                        "explanation": "Alice demo evaluator applied to a paired behavioral test case.",
                        "metadata": metadata,
                    },
                )
            rows.append(
                {
                    "version": config.version,
                    "case": case["name"],
                    "answer_passed": answer_passed,
                    "retrieval_passed": retrieval_passed,
                    "retrieved": result["retrieved_document_ids"],
                }
            )

    paired = http_json(
        "/api/v1/evaluations/compare/paired"
        f"?baseline_version_id={versions[BASELINE.version]['id']}"
        f"&candidate_version_id={versions[CANDIDATE.version]['id']}",
        token=token,
    )
    release = http_json(
        "/api/v1/evaluations/release-decision"
        f"?baseline_version_id={versions[BASELINE.version]['id']}"
        f"&candidate_version_id={versions[CANDIDATE.version]['id']}",
        token=token,
    )

    summary = {
        "alice": {"email": email, "password": password, "workspace_slug": workspace_slug},
        "project": project,
        "versions": versions,
        "dataset": {"id": dataset["id"], "case_count": len(dataset["cases"])},
        "rows": rows,
        "paired_counts": {
            "regressed": len(paired["regressed"]),
            "improved": len(paired["improved"]),
            "unchanged": len(paired["unchanged"]),
            "not_comparable": len(paired["not_comparable"]),
        },
        "release": {
            "decision": release["decision"],
            "summary": release["summary"],
            "reasons": release["reasons"],
        },
        "urls": {
            "login": f"{WEB_URL}/auth?mode=login",
            "release": (
                f"{WEB_URL}/releases?baseline_version_id={versions[BASELINE.version]['id']}"
                f"&candidate_version_id={versions[CANDIDATE.version]['id']}"
            ),
            "runs": f"{WEB_URL}/traces",
            "test_suites": f"{WEB_URL}/datasets",
        },
    }
    out = Path(__file__).with_name("alice_demo_result.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
