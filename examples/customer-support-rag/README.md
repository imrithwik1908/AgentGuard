# Customer Support RAG Reference App

This is a small real-world shaped AI application for validating AgentGuard beyond the deterministic demo.

It answers customer-support policy questions with:

- retrieval over a local policy corpus;
- one order-status tool;
- an OpenAI-compatible chat-completions provider;
- AgentGuard SDK traces for retrieval, tool use, LLM generation, latency, provider metadata, token usage, and failures.

The app can also run with `--mock-provider` for repeatable local smoke tests.

## Environment

```bash
export AGENTGUARD_BASE_URL=http://127.0.0.1:8000
export AGENTGUARD_PROJECT=support-rag
export AGENTGUARD_VERSION=baseline-topk-4
export AGENTGUARD_API_KEY=ag_...

export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini
export RETRIEVAL_TOP_K=4
```

Never commit provider API keys.

## Create Project Versions In AgentGuard

Create a project named `support-rag`, then create at least two versions:

- `baseline-topk-4`
- `candidate-topk-10`

The intended experiment:

- baseline retrieves the top 4 documents;
- candidate retrieves the top 10 documents;
- top 10 can help some broad questions, but can also introduce distractor policy text.

## Run One Real Provider Case

```bash
python examples/customer-support-rag/support_agent.py \
  --question "Can I return an opened laptop after 45 days?" \
  --version baseline-topk-4
```

## Run The Same Suite Against Two Versions

```bash
export RETRIEVAL_TOP_K=4
python examples/customer-support-rag/support_agent.py --version baseline-topk-4

export RETRIEVAL_TOP_K=10
python examples/customer-support-rag/support_agent.py --version candidate-topk-10
```

Then open AgentGuard and compare the baseline and candidate versions. The useful question is not
whether every answer is perfect; it is whether the candidate changed behavior in ways that are
detectable, inspectable, and defensible.

## Local Smoke Test Without Provider Calls

```bash
python examples/customer-support-rag/support_agent.py \
  --mock-provider \
  --case-limit 3 \
  --version baseline-topk-4
```

## Failure Telemetry

These commands intentionally create failed traces:

```bash
python examples/customer-support-rag/support_agent.py \
  --mock-provider \
  --simulate app-failure \
  --question "Can I return an opened laptop after 45 days?"

python examples/customer-support-rag/support_agent.py \
  --simulate provider-timeout \
  --question "Can I return an opened laptop after 45 days?"

python examples/customer-support-rag/support_agent.py \
  --simulate provider-429 \
  --question "Can I return an opened laptop after 45 days?"
```

AgentGuard should show the failed trace, the successful retrieval step before the failure when
applicable, the failed LLM step for provider failures, and the captured exception details.

## Files

- `support_agent.py`: runnable RAG/tool app instrumented with the SDK.
- `corpus.json`: local policy corpus with intentional distractor documents.
- `test_cases.json`: 30 representative customer-support regression cases.
