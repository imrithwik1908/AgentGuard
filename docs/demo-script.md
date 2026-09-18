# AgentGuard v1 Demo Script

Target: 90-120 seconds.

## 1. Setup (15 seconds)

Open **Setup**. Show `support-rag`, `prod-v1`, and `candidate-v2`. Point to the SDK key area: the key
authenticates application telemetry to this workspace and is shown only once.

## 2. Instrumentation (15 seconds)

Show `examples/customer-support-rag/support_agent.py`: `@client.trace_run`, `client.retrieval`,
`client.tool`, and `client.llm_call`. The app provides code and version identity; AgentGuard captures
timing, nested steps, evidence, errors, and model metadata.

## 3. Test Suite (15 seconds)

Open **Test Suites**. Show one case's input and expected answer behavior, source, tool, and latency
constraint. Say: "The developer defines success; they do not write score or release logic."

## 4. Evaluate (10 seconds)

Choose `prod-v1` and `candidate-v2`. Click **Evaluate candidate**. Show queued/running per-evaluator
progress, then allow the app to open Releases when workers finish.

## 5. Compare (20 seconds)

Show the observed `top_k 4 -> 10` change and regressed/improved/unchanged counts. Open one regression
and point out baseline/candidate states, human-readable score, and evaluator category. Do not claim
that `top_k` caused the result.

## 6. Diagnose (20 seconds)

Compare answers, retrieved source IDs, tools, and timing when present. Show the conservative analysis:
the first observed divergence and hypotheses. Open the candidate waterfall and explain that green
steps mean execution succeeded; behavioral checks separately determine correctness.

## 7. Release (10 seconds)

Return to Releases. Show `PASS`, `BLOCK`, or `REVIEW` and backend policy reasons. LLM judges can
supply evidence, but the deterministic release-policy engine makes the recommendation.
