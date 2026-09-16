# Alice's Support Assistant Demo

This folder is a realistic end-user demo application for AgentGuard.

Alice is testing a small customer-support RAG assistant. It is not a real provider call yet, but it
behaves like a versioned LLM app:

- retrieves from a local support-policy corpus;
- generates answers with a deterministic mock LLM;
- instruments each run with the AgentGuard Python SDK;
- creates a project, two versions, a test suite, evaluations, paired comparison evidence, and a
  release decision in AgentGuard.

The version change is intentionally natural:

- `baseline-balanced`: retrieves fewer documents and answers conservatively.
- `candidate-broader-context`: retrieves more documents and gives a more direct answer.

That candidate can help broad questions, but extra context sometimes pulls in distractor policy text.

## Run

From the repository root:

```bash
PYTHONPATH=packages/python-sdk python3 examples/alice-llm-app/run_alice_demo.py
```

The script prints:

- Alice login/workspace info;
- project and version IDs;
- test suite ID;
- per-case baseline/candidate result;
- paired comparison URL;
- release decision URL.

Open the printed Release URL in the AgentGuard website to inspect the result.
