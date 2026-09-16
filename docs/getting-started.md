# Getting Started

This guide walks through AgentGuard as a user would experience it.

Goal:

> Compare a trusted baseline version of an AI application against a changed candidate version and decide whether to ship.

## Prerequisites

Run the local AgentGuard stack:

- Web app: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- API health: `http://127.0.0.1:8000/healthz`

Install the SDK in your AI application:

```bash
python -m pip install agentguard-reliability
```

For local repository development before PyPI publishing:

```bash
python -m pip install -e "/path/to/AgentGuard/packages/python-sdk"
```

## Step 1: Create A Project

Open the web app and go to **Setup**.

Create a project:

- Name: `Support Agent`
- Slug: `support-agent`
- Description: `Customer-support AI application`

A project is one AI application.

## Step 2: Register Versions

Open the project and register two versions:

- `production-v1`: the trusted version.
- `candidate-v2`: the changed version being tested.

The baseline is the version you trust. The candidate is the new version you are evaluating.

## Step 3: Instrument The Application

Wrap one AI application request in an AgentGuard trace:

```python
from agentguard import AgentGuard

client = AgentGuard(
    base_url="http://127.0.0.1:8000",
    project="support-agent",
    version="candidate-v2",
)

with client.trace("answer-support-question", input={"question": question}) as trace:
    with trace.span("retrieve policy documents", type="RETRIEVER", input={"question": question}) as span:
        docs = retrieve(question)
        span.set_output({"documents": docs})

    with trace.span("generate answer", type="LLM", input={"question": question, "documents": docs}) as span:
        answer = generate(question, docs)
        span.set_output({"answer": answer})

    trace.set_output({"answer": answer})
```

Run means one complete execution of the AI app. Step means one recorded operation inside that run.

## Step 4: Create A Test Suite

Go to **Test Suites**.

A test suite is a set of representative cases used to check whether the AI application still behaves correctly after changes.

Example case:

- Input: `Can I return an opened laptop after 45 days?`
- Expected content: `not returnable`

## Step 5: Run Baseline And Candidate

Run the same test case against:

- `production-v1`
- `candidate-v2`

AgentGuard now has paired evidence: the same behavior tested on both versions.

## Step 6: Review Release Decision

Go to **Releases**.

Select:

- Baseline: `production-v1`
- Candidate: `candidate-v2`

AgentGuard classifies test cases as:

- **Regressed**: candidate became worse.
- **Improved**: candidate became better.
- **Unchanged**: behavior stayed equivalent.
- **Not comparable**: one side is missing evidence.

## Step 7: Investigate One Failure

Click **Investigate run** on a regression.

The run investigation page shows:

- what failed;
- which check detected it;
- likely failure area when evidence exists;
- optional execution details.

Open **View execution details** only when you need the trace waterfall, step hierarchy, raw input/output, provider metadata, or error payloads.

## Step 8: Decide

A release decision should mean:

- **Safe to ship**: no paired regressions found.
- **Block: regressions detected**: at least one behavior got worse.
- **Block: runtime failures**: candidate failed while running.
- **Not enough evidence to decide**: the same cases were not run on both versions.
- **Not evaluated yet**: candidate has no evaluation evidence.

AgentGuard should not call missing evidence a regression.
