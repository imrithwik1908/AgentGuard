# AgentGuard

AgentGuard is an AI application evaluation, regression-testing, observability, and release-safety
platform for LLM, RAG, and agentic systems.

AgentGuard v1 is a portfolio/research-grade AI engineering platform, not an enterprise replacement
for mature commercial observability systems.

## What Problem It Solves

Changing a prompt, model, retriever, tool, or workflow can improve average behavior while breaking
individual cases that worked before. AgentGuard reruns representative behaviors against a trusted
baseline and a candidate, shows exactly what changed, and derives an auditable release
recommendation from stored evidence.

The product flow is:

**Instrument -> Run -> Evaluate -> Compare -> Diagnose -> Release**

## Responsibilities

You provide:

- the AI application and its project/version identity;
- representative test cases;
- expected answers, sources, tools, forbidden behavior, schemas, or budgets;
- optional custom evaluators for domain-specific rules.

AgentGuard provides:

- trace and nested-step capture;
- deterministic and rubric-based LLM evaluators;
- background evaluation jobs;
- baseline/candidate pairing and regression classification;
- conservative failure analysis and grouping;
- deterministic release-policy decisions with human-readable reasons.

Users never calculate pass rates, score deltas, regression counts, or release verdicts manually.

## Architecture

```mermaid
flowchart LR
  App[LLM / RAG / agent app] --> SDK[Python SDK]
  SDK --> API[FastAPI API]
  Web[Next.js web app] --> API
  API --> DB[(PostgreSQL)]
  API --> Queue[(Redis)]
  Queue --> Worker[Evaluation worker]
  Worker --> DB
  Worker -. optional .-> Judge[Local Ollama or OpenAI-compatible judge]
```

The API is async FastAPI/SQLAlchemy. PostgreSQL stores workspace ownership, projects, versions,
runs, steps, suites, jobs, evaluator provenance, and comparison evidence. Redis/ARQ separates API
latency from evaluation work. The release engine reads stored results; an LLM never decides whether
to ship.

## Quickstart

Requirements: Docker Desktop and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open the web app at `http://localhost:3000`, API health at `http://localhost:8000/healthz`, and
OpenAPI at `http://localhost:8000/docs`. Register a workspace, create a project and two versions,
then create an SDK key in **Setup**.

Install the SDK from this repository:

```bash
python -m pip install "agentguard-reliability @ git+https://github.com/imrithwik1908/AgentGuard.git#subdirectory=packages/python-sdk"
```

```python
from agentguard import AgentGuard

ag = AgentGuard(
    base_url="http://localhost:8000",
    project="support-agent",
    version="candidate-v2",
    api_key="ag_...",
)

@ag.trace_run("answer-question", input_arg="request")
def answer(*, request):
    with ag.retrieval("retrieve policy", query=request) as step:
        documents = retrieve(request["question"])
        step.set_output({"documents": documents})

    with ag.llm_call("generate answer", provider="openai", model="gpt-4o-mini") as step:
        output = generate(request["question"], documents)
        step.set_output({"answer": output})
    return {"answer": output}
```

Telemetry submission is fail-open by default: an AgentGuard outage logs a structured warning but
does not crash the instrumented application. Set `raise_on_failure=True` only for strict development
or CI behavior.

## Automatic OpenAI-Compatible Instrumentation

```python
from openai import OpenAI
from agentguard.integrations.openai import instrument_openai

openai_client = instrument_openai(OpenAI(), agentguard=ag)

@ag.trace_run("chat", input_arg="request")
def chat(*, request):
    return openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=request["messages"],
    )
```

The wrapper records model/provider, latency, request metadata, response metadata, token usage, and
errors. Provider secrets are never copied into telemetry.

## Real Evaluation Example

[`examples/customer-support-rag`](examples/customer-support-rag) is a 30-case support-policy RAG
application with local document retrieval, an order-status tool, an OpenAI-compatible model path,
and a deterministic mock-provider path. Use `prod-v1` with `top_k=4` and `candidate-v2` with
`top_k=10`, run the same imported suite against both, then click **Evaluate candidate**.

AgentGuard owns evaluator execution and returns paired results as:

- **Regressed**: baseline evidence was better than candidate evidence;
- **Improved**: candidate evidence became better;
- **Unchanged**: no meaningful change beyond the evaluator tolerance;
- **Not comparable**: one version lacks corresponding evidence.

Historical results are not averaged into the current comparison. The unit is evaluation execution,
test case, evaluator, and application version.

## Evaluators

Deterministic behavioral: exact answer, required content, structured output, keyword coverage,
expected tool, and forbidden tool.

Retrieval: required source.

Deterministic operational: runtime success and latency budget.

LLM judge: semantic correctness, groundedness, retrieval relevance, and tool selection. AI results
store evaluator/rubric versions, provider/model, prompt-template version, threshold, score,
explanation, evidence, and timestamp. They are evidence, not ground truth.

## Release Decisions

The release-policy engine uses paired regressions, critical-case regressions, minimum pass rate,
allowed score drop, comparison coverage, runtime failures, and required evaluator evidence.

- `PASS`: complete evidence satisfies policy.
- `BLOCK`: stored evidence violates a configured threshold.
- `REVIEW`: evidence is missing or not sufficient for an automatic decision.

Every decision includes reasons. Failure analysis can summarize observed divergence, but cannot
override evaluator results or the release policy.

## Local AI / Ollama

No paid model API is required. Deterministic-only mode is the default.

```bash
export AGENTGUARD_JUDGE_PROVIDER=ollama
export AGENTGUARD_JUDGE_BASE_URL=http://host.docker.internal:11434
export AGENTGUARD_JUDGE_MODEL=gemma3:4b
docker compose up --build
```

For a natively running API use `http://localhost:11434`. AgentGuard uses Ollama's
OpenAI-compatible `/v1/chat/completions` endpoint and does not require an API key. If Ollama is
unavailable, AI evaluator job cases fail with a structured error; deterministic jobs continue and
missing required evidence produces `REVIEW`, never an invented pass.

This repository does not automatically download or start a model. Choose a model appropriate for
your hardware. A public cloud worker cannot reach Ollama running on a developer laptop unless a
secure network path is deliberately configured.

## Testing

```bash
# API, including PostgreSQL integration tests
cd apps/api
AGENTGUARD_TEST_DATABASE_URL=postgresql+asyncpg://agentguard:agentguard@localhost:55432/agentguard \
  PYTHONPATH=. .venv/bin/pytest -q

# SDK
cd ../../packages/python-sdk
PYTHONPATH=. .venv/bin/pytest -q

# Web
cd ../../apps/web
npm test
npm run lint
npm run build
```

The integration suite covers atomic ingestion, auth/workspace IDOR isolation, demo isolation,
evaluation jobs, evaluator provenance, paired comparison semantics, and release policy behavior.

## Deployment

[`render.yaml`](render.yaml) defines web, API, worker, PostgreSQL, and Redis services. See
[`docs/deployment.md`](docs/deployment.md) for the exact topology, free-demo compromise, environment
variables, migrations, and smoke test.

## Screenshots / Demo

Use [`docs/demo-script.md`](docs/demo-script.md) for a focused 90-120 second product walkthrough.
The authenticated **Load demo data** action creates workspace-isolated, idempotent comparison data.

## Limitations

- No persistent SDK-side retry queue or streaming span ingestion.
- One production-quality provider integration: OpenAI-compatible chat completions.
- Local AI quality depends on the selected model and hardware.
- Failure grouping is deterministic by evaluator/stage, not semantic embedding clustering.
- Release decisions are computed on demand and are not deployment approvals.
- Render's dedicated worker tier is not free; the free demo topology has operational tradeoffs.

## Future Work

Semantic failure clustering, more framework integrations, replay/counterfactual testing,
organization-level RBAC, cursor pagination, generated API clients, and enterprise-scale operations
are intentionally outside v1.

More detail: [`docs/README.md`](docs/README.md).
