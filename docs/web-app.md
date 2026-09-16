# Web App Guide

The AgentGuard web app is the control plane and decision interface.

It is not just a dashboard for SDK traces.

## Overview

Purpose:

> What is happening with my current candidate?

Use Overview to see:

- candidate status;
- regression count;
- improvement count;
- evaluation coverage;
- one recommended next action.

Avoid treating this page as a raw telemetry dashboard. It should answer whether the candidate needs attention.

Recommended user action:

- If there are regressions, click **Review regressions**.
- If there is not enough evidence, run the test suite against both versions.
- If there are no regressions, open **Releases** to review the final decision.

## Setup

Purpose:

> What AI application and versions am I testing?

Use Setup to create:

- projects;
- application versions.

Project means one AI application. Version means one behavior snapshot.

Typical setup:

1. Create project.
2. Register baseline version.
3. Register candidate version.
4. Install SDK in the AI application.
5. Send the first run.

## Test Suites

Purpose:

> What behavior should my AI application preserve?

Use Test Suites to manage representative cases.

Current supported case fields:

- input;
- expected substring/content.

Future case fields may include:

- expected semantic answer;
- expected retrieved source;
- expected tool;
- forbidden behavior;
- latency and cost constraints.

Good test-suite cases are:

- representative of real user behavior;
- tied to an expected behavior;
- stable enough to run repeatedly;
- important enough to block a bad release.

Examples:

| AI application | Useful test case |
| --- | --- |
| Support bot | Refund policy question |
| RAG research assistant | Question requiring a specific source |
| Tool-using agent | Case requiring the correct tool call |
| Structured-output app | Case requiring valid JSON schema |

## Evaluations

Purpose:

> What checks ran, and how did my application perform?

Evaluations are evidence. They are usually not the primary user journey.

Current categories:

- Answer Quality;
- Operational.

Planned categories:

- Retrieval;
- Agent Behavior;
- richer Answer Quality checks.

## Releases

Purpose:

> Should I ship this candidate?

This page compares one baseline version against one candidate version.

The comparison unit is one behavioral test case across two versions.

Results:

- Regressed: candidate became worse.
- Improved: candidate became better.
- Unchanged: no meaningful difference.
- Not comparable: one side is missing evidence.

Release states:

- Safe to ship.
- Block: regressions detected.
- Block: runtime failures.
- Not enough evidence to decide.
- Not evaluated yet.

Interpretation:

- A regression is not just a failed run. It is a paired comparison where the candidate became worse than the baseline.
- Not comparable does not mean failure. It means one side is missing evidence.
- Runtime failures are operational blockers even before answer quality is considered.

## Runs

Purpose:

> What happened inside one execution?

Runs are primarily for investigation.

Use Runs after:

- a regression appears;
- a runtime failure appears;
- you need to inspect retrieval/model/tool behavior.

The run page first shows:

- what failed;
- which checks found evidence;
- likely failure area when supported.

The trace waterfall and step hierarchy are behind **View execution details** because they are advanced debugging evidence.

Use run investigation to answer:

- Did the application retrieve the right context?
- Did the model produce the expected answer?
- Did a tool fail?
- Did latency or runtime errors explain the release blocker?
- Is there enough input/output evidence to debug the issue?

## Docs

Purpose:

> How do I connect my application and understand the product?

Docs include SDK quickstart, product concepts, publishing status, and local workflow.

## Recommended First Demo

For a realistic evaluation flow:

1. Open **Setup** and create a project.
2. Register `production-v1`.
3. Register `candidate-v2`.
4. Instrument a small AI app with the SDK.
5. Create a test suite with one high-signal behavior.
6. Run the behavior against both versions.
7. Open **Releases** and compare baseline against candidate.
8. Investigate one failed run.
