import json
import os
from urllib import request

from agentguard import AgentGuard

DOCUMENTS = [
    {
        "id": "doc-agentguard",
        "title": "AgentGuard",
        "body": "AgentGuard captures traces for LLM, RAG, and agentic applications.",
    },
    {
        "id": "doc-phase-one",
        "title": "Phase 1",
        "body": (
            "Phase 1 focuses on projects, versions, whole-trace ingestion, "
            "and trace exploration."
        ),
    },
    {
        "id": "doc-replay",
        "title": "Counterfactual Replay",
        "body": "Counterfactual replay is a future flagship capability, not part of Phase 1.",
    },
]


def retrieve(question: str) -> list[dict[str, str]]:
    terms = {term.strip("?.!,").lower() for term in question.split()}
    scored = []
    for doc in DOCUMENTS:
        text = f"{doc['title']} {doc['body']}".lower()
        score = sum(1 for term in terms if term and term in text)
        if score:
            scored.append((score, doc))
    return [
        doc for _, doc in sorted(scored, key=lambda item: item[0], reverse=True)
    ] or DOCUMENTS[:1]


def summarize_documents(documents: list[dict[str, str]]) -> dict[str, int]:
    return {
        "document_count": len(documents),
        "character_count": sum(len(doc["body"]) for doc in documents),
    }


def generate_answer(question: str, documents: list[dict[str, str]]) -> str:
    if "fail" in question.lower():
        raise RuntimeError("deterministic demo generation failure requested")
    if os.getenv("DEMO_AGENT_PROVIDER") == "openai-compatible":
        return generate_openai_compatible_answer(question, documents)
    context = " ".join(doc["body"] for doc in documents)
    return f"Based on the local demo corpus: {context}"


def generate_openai_compatible_answer(question: str, documents: list[dict[str, str]]) -> str:
    api_key = os.getenv("DEMO_AGENT_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("DEMO_AGENT_OPENAI_API_KEY is required for openai-compatible mode")
    base_url = os.getenv("DEMO_AGENT_OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("DEMO_AGENT_OPENAI_MODEL", "gpt-4o-mini")
    context = "\n".join(doc["body"] for doc in documents)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Answer only from the supplied local demo corpus.",
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nCorpus:\n{context}",
            },
        ],
        "temperature": 0,
    }
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        body = json.loads(response.read())
    return str(body["choices"][0]["message"]["content"])


def answer_question(client: AgentGuard, question: str) -> str:
    with client.trace("answer-question", input={"question": question}) as trace:
        with trace.span("plan", type="LLM", input={"question": question}) as span:
            plan = {"steps": ["retrieve local documents", "summarize context", "generate answer"]}
            span.set_attributes(
                provider="local",
                model_name="deterministic-planner",
                input_tokens=8,
                output_tokens=12,
            )
            span.set_output(plan)

        with trace.span("retrieve", type="RETRIEVER", input={"query": question}) as span:
            documents = retrieve(question)
            span.set_output({"documents": documents})

            with trace.span(
                "summarize-documents",
                type="TOOL",
                input={"document_ids": [doc["id"] for doc in documents]},
            ) as tool_span:
                summary = summarize_documents(documents)
                tool_span.set_output(summary)

        with trace.span(
            "generate",
            type="LLM",
            input={"question": question, "documents": documents},
        ) as span:
            answer = generate_answer(question, documents)
            span.set_attributes(
                provider="local",
                model_name=os.getenv("DEMO_AGENT_OPENAI_MODEL", "deterministic-generator"),
                input_tokens=64,
                output_tokens=24,
            )
            span.set_output({"answer": answer})

        trace.set_output({"answer": answer})
        return answer
