"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiRequestError, createTraceHealthEvaluation } from "@/lib/api";

function messageFromError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const details = error.details as { message?: unknown } | null;
    if (typeof details?.message === "string") return details.message;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Trace could not be evaluated";
}

export async function createStatusEvaluationAction(traceId: string) {
  try {
    await createTraceHealthEvaluation(traceId);
  } catch (error) {
    const message = encodeURIComponent(messageFromError(error));
    redirect(`/traces/${traceId}?evaluation_error=${message}`);
  }
  revalidatePath(`/traces/${traceId}`);
  revalidatePath("/evaluations");
  revalidatePath("/releases");
  revalidatePath("/");
}
