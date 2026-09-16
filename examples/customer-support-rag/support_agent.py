from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from agentguard import AgentGuard

HERE = Path(__file__).resolve().parent


class ProviderRateLimitError(RuntimeError):
    pass


class ProviderTimeoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    agentguard_base_url: str
    agentguard_project: str
    agentguard_version: str
    agentguard_api_key: str | None
    llm_base_url: str
    llm_api_key: str | None
    llm_model: str
    retrieval_top_k: int
    timeout_seconds: float
    mock_provider: bool

    @classmethod
    def from_env(cls, *, version_override: str | None = None, mock_provider: bool = False) -> Config:
        return cls(
            agentguard_base_url=os.getenv("AGENTGUARD_BASE_URL", "http://127.0.0.1:8000"),
            agentguard_project=os.getenv("AGENTGUARD_PROJECT", "support-rag"),
            agentguard_version=version_override or os.getenv("AGENTGUARD_VERSION", "baseline-topk-4"),
            agentguard_api_key=os.getenv("AGENTGUARD_API_KEY"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "4")),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
            mock_provider=mock_provider or os.getenv("MOCK_LLM_PROVIDER") == "1",
        )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tokenize(text: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9]+", text.lower()) if len(part) > 2}


def retrieve(question: str, corpus: list[dict[str, str]], *, top_k: int) -> list[dict[str, Any]]:
    query_terms = tokenize(question)
    scored: list[tuple[float, dict[str, str]]] = []
    for document in corpus:
        document_terms = tokenize(f"{document['title']} {document['body']}")
        overlap = query_terms & document_terms
        score = len(overlap) / max(len(query_terms), 1)
        if overlap:
            scored.append((score, document))
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]
    return [
        {
            "id": document["id"],
            "title": document["title"],
            "body": document["body"],
            "score": round(score, 4),
        }
        for score, document in ranked
    ]


def extract_order_id(question: str) -> str | None:
    match = re.search(r"\bAG-\d{4}\b", question.upper())
    return match.group(0) if match else None


def lookup_order_status(order_id: str) -> dict[str, Any]:
    orders = {
        "AG-1001": {"status": "shipped", "carrier": "UPS", "eta": "tomorrow"},
        "AG-1002": {"status": "processing", "carrier": None, "eta": "not assigned"},
        "AG-1003": {"status": "delayed", "carrier": "FedEx", "eta": "Friday"},
    }
    if order_id not in orders:
        return {"order_id": order_id, "found": False, "message": "could not find order"}
    return {"order_id": order_id, "found": True, **orders[order_id]}


def build_messages(
    question: str,
    documents: list[dict[str, Any]],
    tool_result: dict[str, Any] | None,
) -> list[dict[str, str]]:
    context = "\n\n".join(
        f"[{doc['id']}] {doc['title']}\n{doc['body']}" for doc in documents
    )
    tool_context = json.dumps(tool_result, indent=2) if tool_result else "No tool result."
    return [
        {
            "role": "system",
            "content": (
                "You are a careful customer-support assistant. Answer only from the provided "
                "policy context and tool result. If the answer is uncertain, say what is missing. "
                "Do not invent order status, refund eligibility, or policy exceptions."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\nPolicy context:\n{context}\n\n"
                f"Tool result:\n{tool_context}"
            ),
        },
    ]


def mock_chat_completion(question: str, documents: list[dict[str, Any]], tool_result: dict[str, Any] | None):
    if tool_result and not tool_result.get("found", True):
        content = f"I could not find order {tool_result['order_id']}. Please verify the order ID."
    elif tool_result and tool_result.get("status"):
        content = (
            f"Order {tool_result['order_id']} is {tool_result['status']}. "
            f"Carrier: {tool_result.get('carrier')}; ETA: {tool_result.get('eta')}."
        )
    else:
        joined = " ".join(document["body"] for document in documents[:2])
        content = f"Based on the retrieved policy: {joined}"
    usage = {"prompt_tokens": 120 + len(documents) * 35, "completion_tokens": len(content.split())}
    return {"content": content, "usage": usage, "raw": {"mock": True, "question": question}}


def call_openai_compatible_chat(
    config: Config,
    messages: list[dict[str, str]],
    *,
    simulate: str | None,
) -> dict[str, Any]:
    if simulate == "provider-timeout":
        time.sleep(min(config.timeout_seconds + 0.1, 1.0))
        raise ProviderTimeoutError("simulated provider timeout")
    if simulate == "provider-429":
        raise ProviderRateLimitError("simulated provider 429 rate limit")
    if not config.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required unless --mock-provider is used")

    body = json.dumps(
        {
            "model": config.llm_model,
            "messages": messages,
            "temperature": 0.1,
        }
    ).encode("utf-8")
    req = request.Request(
        f"{config.llm_base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "authorization": f"Bearer {config.llm_api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 429:
            raise ProviderRateLimitError("provider returned HTTP 429") from exc
        raise RuntimeError(f"provider returned HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout, error.URLError) as exc:
        raise ProviderTimeoutError("provider request timed out or could not connect") from exc

    choice = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage") or {}
    return {"content": choice, "usage": usage, "raw": payload}


def answer_question(config: Config, question: str, *, simulate: str | None = None) -> dict[str, Any]:
    corpus = load_json(HERE / "corpus.json")
    client = AgentGuard(
        base_url=config.agentguard_base_url,
        project=config.agentguard_project,
        version=config.agentguard_version,
        api_key=config.agentguard_api_key,
    )
    with client.trace(
        "support-rag-answer",
        input={"question": question},
        metadata={
            "app": "customer-support-rag",
            "retrieval_top_k": config.retrieval_top_k,
            "llm_provider": "openai-compatible" if not config.mock_provider else "mock",
            "llm_model": config.llm_model,
        },
    ) as trace:
        with trace.span(
            "retrieve policy documents",
            type="RETRIEVER",
            input={"question": question, "top_k": config.retrieval_top_k},
        ) as span:
            documents = retrieve(question, corpus, top_k=config.retrieval_top_k)
            span.set_output({"documents": documents})

        tool_result = None
        order_id = extract_order_id(question)
        if order_id:
            with trace.span(
                "lookup order status",
                type="TOOL",
                input={"order_id": order_id},
                metadata={"tool_name": "order_status"},
            ) as span:
                tool_result = lookup_order_status(order_id)
                span.set_output(tool_result)

        if simulate == "app-failure":
            raise RuntimeError("simulated application failure after retrieval")

        messages = build_messages(question, documents, tool_result)
        with trace.span(
            "generate support answer",
            type="LLM",
            input={"messages": messages, "document_ids": [doc["id"] for doc in documents]},
        ) as span:
            if config.mock_provider:
                completion = mock_chat_completion(question, documents, tool_result)
            else:
                completion = call_openai_compatible_chat(config, messages, simulate=simulate)
            usage = completion["usage"]
            span.set_attributes(
                provider="mock" if config.mock_provider else "openai-compatible",
                model_name=config.llm_model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                finish_reason=completion["raw"].get("choices", [{}])[0].get("finish_reason")
                if isinstance(completion["raw"], dict)
                else None,
            )
            span.set_output({"answer": completion["content"]})

        result = {
            "question": question,
            "answer": completion["content"],
            "retrieved_document_ids": [doc["id"] for doc in documents],
            "tool_result": tool_result,
            "version": config.agentguard_version,
        }
        trace.set_output(result)
        return result


def iter_cases(limit: int | None) -> list[dict[str, Any]]:
    cases = load_json(HERE / "test_cases.json")
    return cases[:limit] if limit else cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AgentGuard customer-support RAG demo.")
    parser.add_argument("--question", help="Run one question instead of the case file.")
    parser.add_argument("--case-limit", type=int, help="Limit the number of cases to run.")
    parser.add_argument("--version", help="Override AGENTGUARD_VERSION.")
    parser.add_argument("--mock-provider", action="store_true", help="Use a deterministic local provider.")
    parser.add_argument(
        "--simulate",
        choices=["app-failure", "provider-timeout", "provider-429"],
        help="Exercise failure telemetry without depending on a provider incident.",
    )
    args = parser.parse_args()
    config = Config.from_env(version_override=args.version, mock_provider=args.mock_provider)

    questions = [{"name": "manual", "question": args.question}] if args.question else iter_cases(args.case_limit)
    failures = 0
    for case in questions:
        try:
            result = answer_question(config, case["question"], simulate=args.simulate)
        except Exception as exc:
            failures += 1
            print(json.dumps({"case": case["name"], "error": type(exc).__name__, "message": str(exc)}))
            continue
        print(json.dumps({"case": case["name"], **result}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
