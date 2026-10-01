# AgentGuard Documentation

AgentGuard is an AI application regression-testing and reliability platform.

It answers one product question:

> I changed something in my AI application. Did it get better or worse, what regressed, why, and should I ship it?

AgentGuard is organized around six steps:

**Instrument -> Run -> Evaluate -> Compare -> Diagnose -> Release**

## Start Here

If you are new to AgentGuard, read these in order:

1. [Getting Started](getting-started.md): build the first local workflow.
2. [How Evaluation Works](evaluations.md): understand evidence, every built-in score, AI judging,
   comparison, diagnosis, and release decisions.
3. [Core Concepts](concepts.md): learn the vocabulary used in the app.
4. [Python SDK](sdk.md): instrument an AI application.
5. [Web App Guide](web-app.md): use the control plane.
6. [Real LLM Demo](real-llm-demo.md): connect a real LLM-backed app.

The evaluation guide is the canonical answer to these questions:

- Which evidence does each check read?
- How is the score calculated?
- Why did a check pass or fail?
- When is an LLM judge used?
- How are historical results prevented from corrupting a comparison?
- Why is a scenario regressed, improved, unchanged, or not comparable?
- How does the release engine reach `PASS`, `BLOCK`, or `REVIEW`?

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
- [How AgentGuard Evaluates An AI Application](evaluations.md)
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
- Redis/ARQ evaluation workers with per-case progress and retries.
- Deterministic and rubric-based LLM evaluator registry.
- Required-source, expected/forbidden-tool, structured-output, and latency checks.
- Local Ollama and external OpenAI-compatible judge adapters.
- Job-scoped paired comparison, failure grouping, and deterministic release policy.

Not implemented in v1:

- Public PyPI upload.
- Embedding-based semantic failure clustering.
- Automatic integrations beyond OpenAI-compatible chat completions.
- Counterfactual replay, enterprise RBAC/scaling, or billing.

AgentGuard should never present planned capabilities as if they are already active.

## Public Links

When the repository is pushed publicly, PyPI will point to:

- Homepage: `https://github.com/imrithwik1908/AgentGuard`
- Documentation: `https://github.com/imrithwik1908/AgentGuard/tree/main/docs`
- Issues: `https://github.com/imrithwik1908/AgentGuard/issues`
