from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib import error, request

from agentguard import AgentGuard
from agentguard.integrations.openai import instrument_openai

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "data" / "meeting_notes.json"
SUITE_PATH = HERE / "test_cases.json"


@dataclass(frozen=True)
class VersionConfig:
    top_k: int
    system_prompt: str


VERSIONS = {
    "prod-v1": VersionConfig(
        top_k=3,
        system_prompt=(
            "Answer the meeting-notes question using only the supplied evidence. Include the "
            "specific owner, date, or decision requested and cite supporting meeting IDs in "
            "square brackets. If evidence is insufficient, state that clearly."
        ),
    ),
    "candidate-v2": VersionConfig(
        top_k=6,
        system_prompt=(
            "Give a concise answer to the question from the supplied meeting notes. Mention the "
            "most relevant decision and cite meeting IDs."
        ),
    ),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def retrieve_notes(question: str, notes: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    query_terms = tokenize(question)
    document_frequency: dict[str, int] = {}
    tokenized_notes: list[list[str]] = []
    for note in notes:
        tokens = tokenize(f"{note['title']} {note['body']}")
        tokenized_notes.append(tokens)
        for term in set(tokens):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    ranked: list[tuple[float, dict[str, Any]]] = []
    for note, tokens in zip(notes, tokenized_notes, strict=True):
        frequencies = {term: tokens.count(term) for term in set(tokens)}
        score = 0.0
        for term in query_terms:
            if term not in frequencies:
                continue
            inverse_frequency = math.log((len(notes) + 1) / (document_frequency[term] + 1)) + 1
            score += (1 + math.log(frequencies[term])) * inverse_frequency
        ranked.append((score, note))

    selected = sorted(ranked, key=lambda item: (-item[0], item[1]["id"]))[:top_k]
    return [
        {
            "id": note["id"],
            "title": note["title"],
            "body": note["body"],
            "score": round(score, 4),
        }
        for score, note in selected
    ]


def lookup_meeting_metadata(
    meeting_ids: list[str], notes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    wanted = set(meeting_ids)
    return [
        {
            "meeting_id": note["id"],
            "date": note["date"],
            "participants": note["participants"],
        }
        for note in notes
        if note["id"] in wanted
    ]


class OpenAICompatibleCompletions:
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def create(self, **payload: Any) -> SimpleNamespace:
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"model provider returned HTTP {exc.code}: {body}") from exc
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"model provider was unreachable: {exc}") from exc
        return response_object(raw)


class OfflineFixtureCompletions:
    """Small extractive fixture for transport smoke tests; it is not an LLM."""

    def create(self, **payload: Any) -> SimpleNamespace:
        messages = payload.get("messages") or []
        user_content = str(messages[-1].get("content", "")) if messages else ""
        question = user_content.partition("Question:\n")[2].partition("\n\nMeeting evidence:")[0]
        evidence = user_content.partition("Meeting evidence:\n")[2].partition(
            "\n\nMeeting metadata tool result:"
        )[0]
        query_terms = set(tokenize(question))
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", evidence) if part]
        ranked = sorted(
            sentences,
            key=lambda sentence: len(query_terms & set(tokenize(sentence))),
            reverse=True,
        )
        content = " ".join(ranked[:4]) or "The supplied meeting evidence is insufficient."
        usage = {
            "prompt_tokens": max(1, len(user_content.split())),
            "completion_tokens": max(1, len(content.split())),
        }
        return response_object(
            {
                "id": f"fixture-{time.time_ns()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": str(payload.get("model", "offline-extractive-fixture")),
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": usage,
            }
        )


class CompatibleClient:
    def __init__(self, completions: Any) -> None:
        self.chat = SimpleNamespace(completions=completions)


def response_object(payload: dict[str, Any]) -> SimpleNamespace:
    choice_objects = [
        SimpleNamespace(
            message=SimpleNamespace(content=choice.get("message", {}).get("content", "")),
            finish_reason=choice.get("finish_reason"),
        )
        for choice in payload.get("choices", [])
    ]
    return SimpleNamespace(
        id=payload.get("id"),
        object=payload.get("object"),
        created=payload.get("created"),
        model=payload.get("model"),
        choices=choice_objects,
        usage=payload.get("usage") or {},
    )


def api_headers(api_key: str) -> dict[str, str]:
    return {"content-type": "application/json", "x-agentguard-api-key": api_key}


def agentguard_request(
    base_url: str,
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    req = request.Request(
        f"{base_url.rstrip('/')}/api/v1{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=api_headers(api_key),
        method=method,
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"AgentGuard returned HTTP {exc.code} for {path}: {body}") from exc


def import_suite(base_url: str, api_key: str, project_id: str) -> dict[str, Any]:
    suite = load_json(SUITE_PATH)
    return agentguard_request(
        base_url,
        api_key,
        "/datasets/import",
        method="POST",
        payload={"project_id": project_id, **suite},
    )


def fetch_suite_cases(base_url: str, api_key: str, dataset_id: str) -> list[dict[str, Any]]:
    suite = agentguard_request(base_url, api_key, f"/datasets/{dataset_id}")
    return [
        {
            "id": case["id"],
            "name": case["name"],
            "question": case["input"]["question"],
        }
        for case in suite.get("cases", [])
    ]


def build_messages(
    question: str,
    documents: list[dict[str, Any]],
    meeting_metadata: list[dict[str, Any]],
    config: VersionConfig,
) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        f"[{document['id']}] {document['title']}\n{document['body']}" for document in documents
    )
    return [
        {"role": "system", "content": config.system_prompt},
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\nMeeting evidence:\n{evidence}\n\n"
                "Meeting metadata tool result:\n"
                f"{json.dumps(meeting_metadata, indent=2)}"
            ),
        },
    ]


def run_case(
    *,
    question: str,
    case_name: str,
    dataset_case_id: str | None,
    version: str,
    offline_fixture: bool,
) -> dict[str, Any]:
    base_url = os.environ["AGENTGUARD_BASE_URL"]
    api_key = os.environ["AGENTGUARD_API_KEY"]
    project = os.environ["AGENTGUARD_PROJECT"]
    model = (
        "offline-extractive-fixture"
        if offline_fixture
        else os.getenv("LLM_MODEL", "gpt-4.1-mini")
    )
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    version_config = VERSIONS[version]
    notes = load_json(CORPUS_PATH)

    agentguard = AgentGuard(
        base_url=base_url,
        project=project,
        version=version,
        api_key=api_key,
        timeout_seconds=10,
    )
    if offline_fixture:
        raw_model_client = CompatibleClient(OfflineFixtureCompletions())
        provider = "offline-fixture"
    else:
        provider_key = os.environ["LLM_API_KEY"]
        provider_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        raw_model_client = CompatibleClient(
            OpenAICompatibleCompletions(
                base_url=provider_url,
                api_key=provider_key,
                timeout_seconds=timeout,
            )
        )
        provider = "openai-compatible"
    model_client = (
        raw_model_client
        if offline_fixture
        else instrument_openai(raw_model_client, agentguard=agentguard)
    )
    trace_input: dict[str, Any] = {"question": question}
    if dataset_case_id:
        trace_input["dataset_case_id"] = dataset_case_id

    @agentguard.trace_run(
        "meeting-notes-question",
        input_arg="trace_input",
        metadata={
            "application": "meeting-notes-assistant",
            "case_name": case_name,
            "dataset_case_id": dataset_case_id,
            "retrieval_top_k": version_config.top_k,
            "model_provider": provider,
            "model": model,
        },
    )
    def execute(*, trace_input: dict[str, Any]) -> dict[str, Any]:
        with agentguard.retrieval(
            "retrieve_meeting_notes",
            query={"question": question, "top_k": version_config.top_k},
            metadata={"algorithm": "tf-idf lexical ranking", "top_k": version_config.top_k},
        ) as span:
            documents = retrieve_notes(question, notes, version_config.top_k)
            span.set_output({"documents": documents})

        meeting_ids = [document["id"] for document in documents]
        with agentguard.tool(
            "lookup_meeting_metadata",
            arguments={"meeting_ids": meeting_ids},
            metadata={"tool_name": "lookup_meeting_metadata"},
        ) as span:
            meeting_metadata = lookup_meeting_metadata(meeting_ids, notes)
            span.set_output({"meetings": meeting_metadata})

        messages = build_messages(question, documents, meeting_metadata, version_config)
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.1 if version == "prod-v1" else 0.3,
        }
        if offline_fixture:
            with agentguard.llm_call(
                "offline_fixture.generate",
                provider=provider,
                model=model,
                input={"messages": messages},
                metadata={"fixture": True},
            ) as span:
                completion = model_client.chat.completions.create(**completion_kwargs)
                span.set_attributes(
                    input_tokens=completion.usage.get("prompt_tokens"),
                    output_tokens=completion.usage.get("completion_tokens"),
                )
                span.set_output({"answer": completion.choices[0].message.content})
        else:
            completion = model_client.chat.completions.create(**completion_kwargs)
        answer = completion.choices[0].message.content
        return {
            "answer": answer,
            "retrieved_document_ids": meeting_ids,
            "tool_result": meeting_metadata,
            "version": version,
        }

    return execute(trace_input=trace_input)


def local_cases() -> list[dict[str, Any]]:
    return [
        {"name": case["name"], "question": case["input"]["question"]}
        for case in load_json(SUITE_PATH)["cases"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Meeting Notes Assistant AgentGuard smoke test")
    parser.add_argument("--version", choices=sorted(VERSIONS), default="prod-v1")
    parser.add_argument("--dataset-id", help="AgentGuard test-suite ID used for paired evaluation")
    parser.add_argument("--question", help="Run one ad hoc question")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument(
        "--offline-fixture",
        action="store_true",
        help="Use the lightweight extractive fixture for plumbing tests; this is not an LLM.",
    )
    parser.add_argument("--import-suite", action="store_true")
    parser.add_argument("--project-id", help="Required with --import-suite")
    args = parser.parse_args()

    required = ["AGENTGUARD_BASE_URL", "AGENTGUARD_API_KEY", "AGENTGUARD_PROJECT"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        parser.error(f"missing environment variables: {', '.join(missing)}")

    if args.import_suite:
        if not args.project_id:
            parser.error("--project-id is required with --import-suite")
        suite = import_suite(
            os.environ["AGENTGUARD_BASE_URL"],
            os.environ["AGENTGUARD_API_KEY"],
            args.project_id,
        )
        print(json.dumps({"dataset_id": suite["id"], "name": suite["name"]}, indent=2))
        return 0

    if not args.offline_fixture and not os.getenv("LLM_API_KEY"):
        parser.error("LLM_API_KEY is required unless --offline-fixture is used")

    if args.question:
        cases = [{"name": "ad-hoc-question", "question": args.question}]
    elif args.dataset_id:
        cases = fetch_suite_cases(
            os.environ["AGENTGUARD_BASE_URL"],
            os.environ["AGENTGUARD_API_KEY"],
            args.dataset_id,
        )
    else:
        cases = local_cases()
    if args.case_limit is not None:
        cases = cases[: args.case_limit]

    failures = 0
    for case in cases:
        try:
            result = run_case(
                question=case["question"],
                case_name=case["name"],
                dataset_case_id=case.get("id"),
                version=args.version,
                offline_fixture=args.offline_fixture,
            )
            print(json.dumps({"case": case["name"], **result}, indent=2))
        except Exception as exc:  # noqa: BLE001 - continue the suite after one case fails.
            failures += 1
            print(
                json.dumps(
                    {"case": case["name"], "error": type(exc).__name__, "message": str(exc)}
                ),
                file=sys.stderr,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
