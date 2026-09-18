# Amy's Incident Briefing Assistant

This external-user example retrieves engineering incident reports, looks up structured incident
metadata, asks an OpenAI-compatible model for an evidence-backed briefing, and records the run
with the public AgentGuard SDK.

It compares `stable-v1` (`top_k=2`, strict prompt) with `candidate-v2` (`top_k=5`, shorter prompt).
AgentGuard, not this application, calculates evaluation results, comparisons, and release status.

```bash
python3.12 -m venv examples/amy-incident-briefing/.venv
source examples/amy-incident-briefing/.venv/bin/activate
python -m pip install packages/python-sdk

export AGENTGUARD_BASE_URL=https://agentguard-api-7evp.onrender.com
export AGENTGUARD_API_KEY='ag_...'
export AGENTGUARD_PROJECT=incident-briefing-assistant
export AGENTGUARD_PROJECT_ID='<project UUID from Setup>'
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY='<provider key>'
export LLM_MODEL=gpt-4.1-mini

python examples/amy-incident-briefing/app.py \
  --import-suite --project-id "$AGENTGUARD_PROJECT_ID"

export AGENTGUARD_DATASET_ID='<dataset ID printed above>'

python examples/amy-incident-briefing/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" --version stable-v1

python examples/amy-incident-briefing/app.py \
  --dataset-id "$AGENTGUARD_DATASET_ID" --version candidate-v2
```

Append `--offline-fixture` when validating the transport and evaluation workflow without a model
credential. Fixture spans are explicitly labeled and are not presented as real LLM inference.
