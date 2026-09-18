# Meeting Notes Assistant Smoke Test

This folder behaves like a small external application owned by a user named Bryan. It retrieves
from local meeting notes, looks up meeting dates and participants with a tool, sends the resulting
evidence to an OpenAI-compatible chat-completions endpoint, and records the complete run through
the public AgentGuard Python SDK.

The experiment compares two plausible application configurations:

| Version | Retrieval | Generation behavior |
| --- | --- | --- |
| `prod-v1` | top 3 notes | strict evidence-only prompt, lower temperature |
| `candidate-v2` | top 6 notes | shorter prompt, slightly higher temperature |

The application supplies traces and declarative expectations. It never calculates evaluation
scores, comparison counts, regressions, or a release decision; AgentGuard owns those operations.

## 1. Install

From the AgentGuard repository root, create an isolated environment and install the public SDK
package from this checkout:

```bash
python3.12 -m venv examples/real-user-smoke-test/.venv
source examples/real-user-smoke-test/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install packages/python-sdk
```

No heavyweight local model is installed. The standard-library model client works with an
OpenAI-compatible `/chat/completions` endpoint already supported by AgentGuard.

## 2. Create Bryan's AgentGuard Resources

Sign in to AgentGuard as Bryan. In **Setup**:

1. Create a project named **Meeting Notes Assistant** with slug `meeting-notes-assistant`.
2. Create version `prod-v1` with retrieval configuration `{"top_k": 3}`.
3. Create version `candidate-v2` with retrieval configuration `{"top_k": 6}`.
4. Create and copy a workspace API key. It is only shown once.

Export the connection values. `AGENTGUARD_PROJECT` is the project slug, while
`AGENTGUARD_PROJECT_ID` is the UUID shown by the project API/UI.

```bash
export AGENTGUARD_BASE_URL=https://agentguard-api-7evp.onrender.com
export AGENTGUARD_API_KEY='ag_...'
export AGENTGUARD_PROJECT=meeting-notes-assistant
export AGENTGUARD_PROJECT_ID='00000000-0000-0000-0000-000000000000'
```

Configure any OpenAI-compatible provider. Do not commit this key.

```bash
export LLM_BASE_URL='https://api.openai.com/v1'
export LLM_API_KEY='your-provider-key'
export LLM_MODEL='gpt-4.1-mini'
```

## 3. Import The Test Suite

The import sends inputs, expectations, and evaluator names. It does not send scores.

```bash
python examples/real-user-smoke-test/app.py \
  --import-suite \
  --project-id "$AGENTGUARD_PROJECT_ID"
```

Copy the returned `dataset_id`:

```bash
export AGENTGUARD_DATASET_ID='00000000-0000-0000-0000-000000000000'
```

## 4. Run `prod-v1`

```bash
python examples/real-user-smoke-test/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" \
  --version prod-v1
```

## 5. Run `candidate-v2`

```bash
python examples/real-user-smoke-test/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" \
  --version candidate-v2
```

Each command runs all eight cases and generates one trace per case. Every trace includes a
retrieval step, `lookup_meeting_metadata` tool step, instrumented model call, answer, source IDs,
timing, provider/model metadata, and token usage when the provider returns it.

## 6. Evaluate In AgentGuard

Open **Test Suites**, select **Meeting Notes Regression Suite**, choose `prod-v1` as the trusted
baseline and `candidate-v2` as the candidate, then click **Evaluate candidate**. AgentGuard's
worker runs the configured checks, pairs the same cases across versions, classifies results, and
derives the release recommendation from stored evidence.

Continue through **Compare** to review regressed, improved, unchanged, or not-comparable cases.
Open a case to compare answers, retrieved sources, tool behavior, and execution evidence. Use
**Runs** only when you need the complete trace and step waterfall.

## Offline Plumbing Check

When provider credentials are unavailable, append `--offline-fixture`. This exercises the same
retrieval, tool, SDK, and ingestion path using a generic extractive fixture and an explicitly
labeled fixture span. It is not evidence that a real LLM provider works.

```bash
python examples/real-user-smoke-test/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" \
  --version prod-v1 \
  --offline-fixture
```

## Files

- `app.py`: runnable external application and suite-import utility.
- `data/meeting_notes.json`: local retrieval corpus.
- `test_cases.json`: eight declarative behavioral cases.
