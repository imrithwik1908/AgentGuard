from __future__ import annotations

import argparse
import functools
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
DOCUMENTS = HERE / "data" / "security_documents.json"
CONTROLS = HERE / "data" / "control_registry.json"
SUITE = HERE / "test_cases.json"
HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class VersionConfig:
    top_k: int
    temperature: float
    prompt: str


VERSIONS = {
    "approved-v1": VersionConfig(
        top_k=3,
        temperature=0.1,
        prompt=(
            "Answer the vendor-security question only from the supplied evidence. Prefer current "
            "approved policies over archived material. Give exact limits, owners, and deadlines, "
            "cite document IDs, and explicitly identify any unresolved gap."
        ),
    ),
    "candidate-v2": VersionConfig(
        top_k=6,
        temperature=0.3,
        prompt=(
            "Write a concise vendor-risk answer from the supplied documents. Cite document IDs "
            "and include the most relevant operational details."
        ),
    ),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def retrieve(question: str, documents: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    query_tokens = tokens(question)
    document_tokens = [
        tokens(f"{document['title']} {document['body']}") for document in documents
    ]
    frequencies: dict[str, int] = {}
    for words in document_tokens:
        for word in set(words):
            frequencies[word] = frequencies.get(word, 0) + 1

    scored: list[tuple[float, dict[str, Any]]] = []
    for document, words in zip(documents, document_tokens, strict=True):
        score = sum(
            math.log((len(documents) + 1) / (frequencies[word] + 1)) + 1
            for word in query_tokens
            if word in words
        )
        scored.append((score, document))

    ranked = sorted(scored, key=lambda item: (-item[0], item[1]["id"]))[:top_k]
    return [
        {
            "id": document["id"],
            "title": document["title"],
            "status": document["status"],
            "body": document["body"],
            "control_ids": document["control_ids"],
            "score": round(score, 4),
        }
        for score, document in ranked
    ]


def lookup_control_owners(control_ids: list[str], registry: list[dict[str, Any]]) -> list[dict]:
    selected = set(control_ids)
    return [control for control in registry if control["control_id"] in selected]


def provider_completion(messages: list[dict[str, str]], model: str, temperature: float) -> dict:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature}
    ).encode("utf-8")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "authorization": f"Bearer {os.environ['LLM_API_KEY']}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(
            req,
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
            context=HTTPS_CONTEXT,
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:2000]
        try:
            provider_error = json.loads(body).get("error", {})
            detail = ", ".join(
                f"{key}={provider_error[key]}"
                for key in ("message", "type", "code")
                if provider_error.get(key)
            )
        except (AttributeError, json.JSONDecodeError):
            detail = body.strip()[:500]
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"model provider returned HTTP {exc.code}{suffix}") from exc
    except (OSError, TimeoutError) as exc:
        raise RuntimeError(f"model provider was unreachable: {exc}") from exc
    return {
        "answer": result["choices"][0]["message"]["content"],
        "usage": result.get("usage") or {},
    }


@functools.lru_cache(maxsize=1)
def load_local_model(model_id: str):
    try:
        from mlx_lm import load
    except ImportError as exc:
        raise RuntimeError(
            "local model support requires: python -m pip install mlx-lm"
        ) from exc
    return load(model_id)


def local_completion(messages: list[dict[str, str]], model_id: str) -> dict:
    from mlx_lm import generate

    model, tokenizer = load_local_model(model_id)
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    answer = generate(model, tokenizer, prompt=prompt, max_tokens=220, verbose=False).strip()
    return {
        "answer": answer,
        "usage": {
            "prompt_tokens": len(tokenizer.encode(prompt)),
            "completion_tokens": len(tokenizer.encode(answer)),
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
        with request.urlopen(req, timeout=30, context=HTTPS_CONTEXT) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"AgentGuard returned HTTP {exc.code}: {detail}") from exc


def build_messages(
    question: str,
    evidence: str,
    controls: list[dict[str, Any]],
    config: VersionConfig,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": config.prompt},
        {
            "role": "user",
            "content": (
                f"Security review question:\n{question}\n\n"
                f"Retrieved documents:\n{evidence}\n\n"
                f"Control-owner lookup:\n{json.dumps(controls, indent=2)}"
            ),
        },
    ]


def run_case(
    case: dict[str, Any],
    version: str,
    local_model: str | None,
) -> dict[str, Any]:
    config = VERSIONS[version]
    documents = read_json(DOCUMENTS)
    registry = read_json(CONTROLS)
    question = case["question"]
    if local_model:
        provider = "local-mlx"
        model = local_model
    else:
        provider = "openai-compatible"
        model = os.getenv("LLM_MODEL", "gpt-4.1-mini")

    client = AgentGuard(
        base_url=os.environ["AGENTGUARD_BASE_URL"],
        project=os.environ["AGENTGUARD_PROJECT"],
        version=version,
        api_key=os.environ["AGENTGUARD_API_KEY"],
        timeout_seconds=15,
    )
    trace_input = {"question": question, "dataset_case_id": case.get("id")}

    @client.trace_run(
        "vendor-security-question",
        input_arg="trace_input",
        metadata={
            "application": "vendor-risk-assistant",
            "dataset_case_id": case.get("id"),
            "retrieval_top_k": config.top_k,
            "provider": provider,
            "model": model,
        },
    )
    def execute(*, trace_input: dict[str, Any]) -> dict[str, Any]:
        with client.retrieval(
            "retrieve_security_documents",
            query={"question": question, "top_k": config.top_k},
            metadata={"algorithm": "tf-idf lexical ranking"},
        ) as span:
            retrieved = retrieve(question, documents, config.top_k)
            span.set_output({"documents": retrieved})

        control_ids = sorted(
            {control_id for document in retrieved for control_id in document["control_ids"]}
        )
        with client.tool(
            "lookup_control_owner",
            arguments={"control_ids": control_ids},
        ) as span:
            controls = lookup_control_owners(control_ids, registry)
            span.set_output({"controls": controls})

        evidence = "\n\n".join(
            f"[{document['id']}] ({document['status']}) {document['title']}\n{document['body']}"
            for document in retrieved
        )
        messages = build_messages(question, evidence, controls, config)
        with client.llm_call(
            "generate_vendor_risk_answer",
            provider=provider,
            model=model,
            input={"messages": messages},
        ) as span:
            completion = (
                local_completion(messages, model)
                if local_model
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
            "retrieved_document_ids": [document["id"] for document in retrieved],
            "version": version,
        }

    return execute(trace_input=trace_input)


def cases_from_suite(dataset_id: str | None) -> list[dict[str, Any]]:
    if dataset_id:
        suite = api_request(f"/datasets/{dataset_id}")
        return [
            {
                "id": item["id"],
                "name": item["name"],
                "question": item["input"]["question"],
            }
            for item in suite["cases"]
        ]
    return [
        {"name": item["name"], "question": item["input"]["question"]}
        for item in read_json(SUITE)["cases"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Emma's vendor-risk AgentGuard example")
    parser.add_argument("--version", choices=sorted(VERSIONS), default="approved-v1")
    parser.add_argument("--dataset-id")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument(
        "--local-model",
        nargs="?",
        const="mlx-community/Qwen2.5-0.5B-Instruct-4bit",
        help="use the small real MLX model; optionally supply another MLX model ID",
    )
    parser.add_argument("--import-suite", action="store_true")
    parser.add_argument("--project-id")
    args = parser.parse_args()

    required = ["AGENTGUARD_BASE_URL", "AGENTGUARD_API_KEY", "AGENTGUARD_PROJECT"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        parser.error(f"missing environment variables: {', '.join(missing)}")
    if not args.local_model and not args.import_suite and not os.getenv("LLM_API_KEY"):
        parser.error("LLM_API_KEY is required unless --local-model is used")

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
            result = run_case(case, args.version, args.local_model)
            print(json.dumps({"case": case["name"], **result}, indent=2))
        except Exception as exc:  # noqa: BLE001 - preserve later smoke cases.
            failures += 1
            print(json.dumps({"case": case["name"], "error": str(exc)}), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
