from __future__ import annotations

import argparse
import json
import math
import os
import re
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

import certifi
from agentguard import AgentGuard

HERE = Path(__file__).resolve().parent
HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())
CORPUS = HERE / "data" / "incidents.json"
SUITE = HERE / "test_cases.json"


@dataclass(frozen=True)
class VersionConfig:
    top_k: int
    prompt: str
    temperature: float


VERSIONS = {
    "stable-v1": VersionConfig(
        top_k=2,
        temperature=0.1,
        prompt=(
            "Answer only from the supplied incident evidence. State the requested owner, cause, "
            "mitigation, or deadline precisely and cite incident IDs. Say when evidence is missing."
        ),
    ),
    "candidate-v2": VersionConfig(
        top_k=5,
        temperature=0.3,
        prompt="Write a concise incident briefing from the supplied evidence and cite incident IDs.",
    ),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tokens(text: str) -> list[str]:
    return [part for part in re.findall(r"[a-z0-9]+", text.lower()) if len(part) > 2]


def retrieve(question: str, documents: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    query = tokens(question)
    frequencies: dict[str, int] = {}
    document_tokens = [tokens(f"{item['title']} {item['body']}") for item in documents]
    for words in document_tokens:
        for word in set(words):
            frequencies[word] = frequencies.get(word, 0) + 1
    scored = []
    for document, words in zip(documents, document_tokens, strict=True):
        score = sum(
            (math.log((len(documents) + 1) / (frequencies[word] + 1)) + 1)
            for word in query
            if word in words
        )
        scored.append((score, document))
    ranked = sorted(scored, key=lambda item: (-item[0], item[1]["id"]))[:top_k]
    return [
        {
            "id": document["id"],
            "title": document["title"],
            "body": document["body"],
            "score": round(score, 4),
        }
        for score, document in ranked
    ]


def lookup_incident_metadata(ids: list[str], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = set(ids)
    return [
        {
            "incident_id": item["id"],
            "date": item["date"],
            "severity": item["severity"],
            "owner": item["owner"],
        }
        for item in documents
        if item["id"] in selected
    ]


def provider_completion(messages: list[dict[str, str]], model: str, temperature: float) -> dict:
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature}
    ).encode("utf-8")
    url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = request.Request(
        f"{url}/chat/completions",
        data=body,
        headers={
            "authorization": f"Bearer {os.environ['LLM_API_KEY']}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(
            req,
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            context=HTTPS_CONTEXT,
        ) as reply:
            payload = json.loads(reply.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"model provider returned HTTP {exc.code}") from exc
    except (OSError, TimeoutError) as exc:
        raise RuntimeError(f"model provider was unreachable: {exc}") from exc
    return {
        "answer": payload["choices"][0]["message"]["content"],
        "usage": payload.get("usage") or {},
    }


def fixture_completion(question: str, evidence: str) -> dict:
    query = set(tokens(question))
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", evidence) if part]
    ranked = sorted(
        sentences,
        key=lambda sentence: len(query & set(tokens(sentence))),
        reverse=True,
    )
    answer = " ".join(ranked[:4]) or "The supplied incident evidence is insufficient."
    return {
        "answer": answer,
        "usage": {
            "prompt_tokens": max(1, len(evidence.split())),
            "completion_tokens": max(1, len(answer.split())),
        },
    }


def api_request(path: str, *, method: str = "GET", payload: dict | None = None) -> Any:
    base_url = os.environ["AGENTGUARD_BASE_URL"].rstrip("/")
    req = request.Request(
        f"{base_url}/api/v1{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "content-type": "application/json",
            "x-agentguard-api-key": os.environ["AGENTGUARD_API_KEY"],
        },
        method=method,
    )
    try:
        with request.urlopen(req, timeout=20, context=HTTPS_CONTEXT) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"AgentGuard returned HTTP {exc.code}: {detail}") from exc


def build_messages(question: str, evidence: str, metadata: list[dict], config: VersionConfig):
    return [
        {"role": "system", "content": config.prompt},
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\nIncident evidence:\n{evidence}\n\n"
                f"Incident metadata:\n{json.dumps(metadata, indent=2)}"
            ),
        },
    ]


def run_case(case: dict[str, Any], version: str, offline_fixture: bool) -> dict[str, Any]:
    config = VERSIONS[version]
    documents = read_json(CORPUS)
    question = case["question"]
    model = "offline-extractive-fixture" if offline_fixture else os.getenv(
        "LLM_MODEL", "gpt-4.1-mini"
    )
    provider = "offline-fixture" if offline_fixture else "openai-compatible"
    client = AgentGuard(
        base_url=os.environ["AGENTGUARD_BASE_URL"],
        project=os.environ["AGENTGUARD_PROJECT"],
        version=version,
        api_key=os.environ["AGENTGUARD_API_KEY"],
        timeout_seconds=10,
    )
    trace_input = {"question": question, "dataset_case_id": case.get("id")}

    @client.trace_run(
        "incident-briefing-question",
        input_arg="trace_input",
        metadata={
            "application": "incident-briefing-assistant",
            "dataset_case_id": case.get("id"),
            "retrieval_top_k": config.top_k,
            "provider": provider,
            "model": model,
        },
    )
    def execute(*, trace_input: dict[str, Any]) -> dict[str, Any]:
        with client.retrieval(
            "retrieve_incident_reports",
            query={"question": question, "top_k": config.top_k},
            metadata={"algorithm": "tf-idf lexical ranking"},
        ) as span:
            retrieved = retrieve(question, documents, config.top_k)
            span.set_output({"documents": retrieved})

        ids = [item["id"] for item in retrieved]
        with client.tool("lookup_incident_metadata", arguments={"incident_ids": ids}) as span:
            metadata = lookup_incident_metadata(ids, documents)
            span.set_output({"incidents": metadata})

        evidence = "\n\n".join(
            f"[{item['id']}] {item['title']}\n{item['body']}" for item in retrieved
        )
        messages = build_messages(question, evidence, metadata, config)
        with client.llm_call(
            "generate_incident_briefing",
            provider=provider,
            model=model,
            input={"messages": messages},
        ) as span:
            completion = (
                fixture_completion(question, evidence)
                if offline_fixture
                else provider_completion(messages, model, config.temperature)
            )
            usage = completion["usage"]
            span.set_attributes(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            span.set_output({"answer": completion["answer"]})

        return {
            "answer": completion["answer"],
            "retrieved_document_ids": ids,
            "version": version,
        }

    return execute(trace_input=trace_input)


def cases_from_suite(dataset_id: str | None) -> list[dict[str, Any]]:
    if dataset_id:
        suite = api_request(f"/datasets/{dataset_id}")
        return [
            {"id": item["id"], "name": item["name"], "question": item["input"]["question"]}
            for item in suite["cases"]
        ]
    return [
        {"name": item["name"], "question": item["input"]["question"]}
        for item in read_json(SUITE)["cases"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Amy's incident-briefing AgentGuard example")
    parser.add_argument("--version", choices=sorted(VERSIONS), default="stable-v1")
    parser.add_argument("--dataset-id")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--offline-fixture", action="store_true")
    parser.add_argument("--import-suite", action="store_true")
    parser.add_argument("--project-id")
    args = parser.parse_args()

    required = ["AGENTGUARD_BASE_URL", "AGENTGUARD_API_KEY", "AGENTGUARD_PROJECT"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        parser.error(f"missing environment variables: {', '.join(missing)}")
    if not args.offline_fixture and not args.import_suite and not os.getenv("LLM_API_KEY"):
        parser.error("LLM_API_KEY is required unless --offline-fixture is used")

    if args.import_suite:
        if not args.project_id:
            parser.error("--project-id is required with --import-suite")
        suite = api_request(
            "/datasets/import",
            method="POST",
            payload={"project_id": args.project_id, **read_json(SUITE)},
        )
        print(json.dumps({"dataset_id": suite["id"], "name": suite["name"]}, indent=2))
        return 0

    cases = cases_from_suite(args.dataset_id)
    if args.case_limit:
        cases = cases[: args.case_limit]
    failures = 0
    for case in cases:
        try:
            print(
                json.dumps(
                    {"case": case["name"], **run_case(case, args.version, args.offline_fixture)},
                    indent=2,
                )
            )
        except Exception as exc:  # noqa: BLE001 - preserve later smoke cases.
            failures += 1
            print(json.dumps({"case": case["name"], "error": str(exc)}), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
