# AgentGuard Documentation

AgentGuard is an AI application regression-testing and reliability platform.

It answers one product question:

> I changed something in my AI application. Did it get better or worse, what regressed, why, and should I ship it?

AgentGuard is organized around five verbs:

**Instrument → Test → Evaluate → Investigate → Release**

## Start Here

If you are new to AgentGuard, read these in order:

1. [Getting Started](getting-started.md): build the first local workflow.
2. [Core Concepts](concepts.md): learn the vocabulary used in the app.
3. [Python SDK](sdk.md): instrument an AI application.
4. [Web App Guide](web-app.md): use the control plane.
5. [Real LLM Demo](real-llm-demo.md): connect a real LLM-backed app.

## Documentation Structure

These docs follow the Diátaxis documentation model:

- **Tutorials** help you learn by completing a guided workflow.
- **How-to guides** help you accomplish a specific goal.
- **Reference** gives exact technical details.
- **Explanation** builds conceptual understanding.

### Tutorials

- [Getting Started](getting-started.md)
- [Real LLM Demo](real-llm-demo.md)

### How-To Guides

- [Web App Guide](web-app.md)
- [SDK Publishing](sdk-publishing.md)

### Reference

- [Python SDK](sdk.md)
- [API Reference](api-reference.md)
- [Configuration Reference](configuration.md)

### Explanation

- [Core Concepts](concepts.md)
- [Evaluations](evaluations.md)
- [Troubleshooting](troubleshooting.md)

## What Exists Today

Implemented:

- Python SDK instrumentation.
- Whole-run ingestion into the backend.
- Project and version tracking.
- Test suites backed by dataset records.
- Deterministic answer/content checks.
- Operational checks for runtime status, nested step errors, latency, and debuggability.
- Baseline-vs-candidate comparison in the web app.
- Regression-first release workflow.
- Run investigation with trace waterfall and step details.

Not implemented yet:

- Hosted public deployment.
- Public PyPI upload.
- Semantic LLM-judge evaluators.
- Groundedness and hallucination detection.
- Retrieval relevance/coverage evaluators.
- Tool-selection evaluators.
- AI-assisted failure clustering.
- Persistent queues or enterprise billing.

AgentGuard should never present planned capabilities as if they are already active.

## Public Links

When the repository is pushed publicly, PyPI will point to:

- Homepage: `https://github.com/csairithwikreddy/AgentGuard`
- Documentation: `https://github.com/csairithwikreddy/AgentGuard/tree/main/docs`
- Issues: `https://github.com/csairithwikreddy/AgentGuard/issues`
