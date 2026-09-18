# Emma's Vendor Security Review Assistant

This is a small real LLM/RAG application for testing AgentGuard as an external user. It retrieves
from current, archived, and draft vendor-security documents, looks up structured control ownership,
and asks a language model for an evidence-backed response. It contains no hardcoded answer routing.

The versions represent a plausible engineering change:

- `approved-v1`: `top_k=3`, low temperature, strict current-policy prompt.
- `candidate-v2`: `top_k=6`, higher temperature, shorter executive-answer prompt.

AgentGuard, not this application, runs the declared checks, pairs results, classifies changes, and
produces the release recommendation.

## Install

From the AgentGuard repository root:

```bash
python3.12 -m venv examples/emma-vendor-risk-assistant/.venv
source examples/emma-vendor-risk-assistant/.venv/bin/activate
python -m pip install packages/python-sdk mlx-lm
```

The default local model is `mlx-community/Qwen2.5-0.5B-Instruct-4bit`. It is a real quantized LLM,
downloads once, runs locally on Apple Silicon, and requires no provider key.

## Configure AgentGuard

```bash
export AGENTGUARD_BASE_URL='https://agentguard-api-7evp.onrender.com'
export AGENTGUARD_API_KEY='ag_...'
export AGENTGUARD_PROJECT='vendor-risk-assistant'
export AGENTGUARD_PROJECT_ID='<project UUID from Setup>'
```

## Import and run

```bash
python examples/emma-vendor-risk-assistant/app.py \
  --import-suite --project-id "$AGENTGUARD_PROJECT_ID"

export AGENTGUARD_DATASET_ID='<dataset ID printed above>'

python examples/emma-vendor-risk-assistant/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" --version approved-v1 --local-model

python examples/emma-vendor-risk-assistant/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" --version candidate-v2 --local-model
```

To use an external OpenAI-compatible provider instead, omit `--local-model` and configure
`LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
