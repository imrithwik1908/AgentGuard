# Real LLM Demo

This guide shows how an average AI developer would use AgentGuard with a real LLM-backed application.

The goal is not to trace a fake dashboard. The goal is to create an AI app, connect the SDK, run a baseline and a candidate, evaluate behavior, and use the web app to decide whether to ship.

## What You Will Build

A tiny support-answering application:

- receives a customer question;
- retrieves a short policy document;
- calls an LLM;
- returns an answer;
- records the run and steps in AgentGuard.

## Environment

```bash
mkdir -p ~/agentguard-real-llm-demo
cd ~/agentguard-real-llm-demo

python3 -m venv .venv
source .venv/bin/activate

python -m pip install agentguard-reliability openai
```

Before public SDK publishing, install from the local repo:

```bash
python -m pip install -e "/Users/csairithwikreddy/Documents/ChatGPT/AgentGuard/packages/python-sdk"
python -m pip install openai
```

Set environment variables:

```bash
export AGENTGUARD_API_URL="http://127.0.0.1:8000"
export AGENTGUARD_PROJECT="support-agent"
export AGENTGUARD_VERSION="production-v1"
export OPENAI_API_KEY="your-openai-key"
```

## Application Code

Create `support_agent.py`:

```python
import os
from decimal import Decimal

from agentguard import AgentGuard
from openai import OpenAI


POLICIES = [
    {
        "id": "returns-general",
        "text": "Most unopened electronics can be returned within 30 days with a receipt.",
    },
    {
        "id": "opened-laptop-policy",
        "text": "Opened laptops are not returnable after 14 days unless they are defective.",
    },
]


def retrieve(question: str, version: str) -> list[dict]:
    lowered = question.lower()
    if version == "candidate-v2" and "opened laptop" in lowered:
        # Intentional retrieval regression for the demo.
        return [POLICIES[0]]
    if "opened laptop" in lowered:
        return [POLICIES[1]]
    return [POLICIES[0]]


def generate(question: str, docs: list[dict]) -> str:
    client = OpenAI()
    context = "\n".join(f"- {doc['text']}" for doc in docs)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful support agent. Answer only from the policy context. "
                    "If the policy says an item is not returnable, say so clearly."
                ),
            },
            {
                "role": "user",
                "content": f"Policy context:\n{context}\n\nQuestion: {question}",
            },
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


def answer(question: str) -> str:
    version = os.getenv("AGENTGUARD_VERSION", "production-v1")
    guard = AgentGuard(
        base_url=os.getenv("AGENTGUARD_API_URL", "http://127.0.0.1:8000"),
        project=os.getenv("AGENTGUARD_PROJECT", "support-agent"),
        version=version,
    )

    with guard.trace("answer-support-question", input={"question": question}) as trace:
        with trace.span("retrieve policy context", type="RETRIEVER", input={"question": question}) as span:
            docs = retrieve(question, version)
            span.set_output({"documents": docs})
            span.set_attributes(top_k=len(docs))

        with trace.span("generate answer", type="LLM", input={"question": question, "documents": docs}) as span:
            result = generate(question, docs)
            span.set_attributes(
                provider="openai",
                model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                estimated_cost=Decimal("0.0000"),
            )
            span.set_output({"answer": result})

        trace.set_output({"answer": result})
        return result


if __name__ == "__main__":
    print(answer("Can I return an opened laptop after 45 days?"))
```

## Run Baseline

```bash
export AGENTGUARD_VERSION="production-v1"
python support_agent.py
```

Open **Runs** in AgentGuard. You should see a successful run.

## Run Candidate

```bash
export AGENTGUARD_VERSION="candidate-v2"
python support_agent.py
```

Open **Runs** again. You should see another run for the candidate.

## Evaluate

Create a test suite in **Test Suites** or through the API with:

- input: `Can I return an opened laptop after 45 days?`
- expected content: `not returnable`

Run the same case against both versions.

## Compare

Open **Releases**.

Select:

- Baseline: `production-v1`
- Candidate: `candidate-v2`

Expected result:

- candidate retrieved the wrong policy context;
- candidate answer is worse;
- AgentGuard should show a regression if the deterministic expected-content check fails.

## Investigate

Click **Investigate run**.

Open **View execution details**.

Look for:

- retrieval step output;
- generated answer;
- provider/model metadata;
- any captured errors.

## Production Notes

For real production use:

- use stable project slugs and version names;
- pass real provider/model/token/cost metadata when available;
- create test suites from real failure cases and important customer journeys;
- keep deterministic checks for high-signal regressions;
- add semantic/grounding/tool evaluators when implemented.
