"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiRequestError, createDataset, runDatasetCase } from "@/lib/api";

function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return encodeURIComponent(error.message);
  }
  return encodeURIComponent(error instanceof Error ? error.message : String(error));
}

export async function createDemoDatasetAction(formData: FormData) {
  const projectId = String(formData.get("project_id") ?? "");
  if (!projectId) {
    redirect("/datasets?dataset_error=Choose a project before creating a test suite");
  }

  try {
    await createDataset({
      project_id: projectId,
      name: "Demo Agent Golden Set",
      slug: `demo-agent-golden-${Date.now()}`,
      description: "Deterministic questions the demo agent should keep answering correctly.",
      cases: [
        {
          name: "explains-agentguard",
          input: { question: "What is AgentGuard?" },
          expected_substring: "captures traces"
        },
        {
          name: "explains-phase-one",
          input: { question: "What does Phase 1 focus on?" },
          expected_substring: "whole-trace ingestion"
        },
        {
          name: "intentional-regression-check",
          input: { question: "What is AgentGuard?" },
          expected_substring: "this phrase will not appear"
        }
      ]
    });
  } catch (error) {
    redirect(`/datasets?dataset_error=${errorMessage(error)}`);
  }

  revalidatePath("/datasets");
  redirect("/datasets");
}

export async function runDatasetCaseAction(formData: FormData) {
  const caseId = String(formData.get("case_id") ?? "");
  const versionId = String(formData.get("application_version_id") ?? "");
  if (!caseId || !versionId) {
    redirect("/datasets?dataset_error=Choose a case and version before running a check");
  }

  let traceId = "";
  try {
    const result = await runDatasetCase(caseId, versionId);
    traceId = result.trace.id;
  } catch (error) {
    redirect(`/datasets?dataset_error=${errorMessage(error)}`);
  }

  revalidatePath("/datasets");
  revalidatePath("/evaluations");
  revalidatePath("/releases");
  revalidatePath("/traces");
  redirect(`/traces/${traceId}`);
}
