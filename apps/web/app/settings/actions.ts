"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, createApiKey } from "@/lib/api";
import type { ApiKey } from "@/lib/types";

export interface CreateApiKeyState {
  status: "idle" | "created" | "error";
  apiKey?: string;
  record?: ApiKey;
  message?: string;
}

function messageFromError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const details = error.details as { message?: unknown } | null;
    if (typeof details?.message === "string") return details.message;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

export async function createApiKeyAction(
  _previous: CreateApiKeyState,
  formData: FormData
): Promise<CreateApiKeyState> {
  const workspaceId = String(formData.get("workspace_id") ?? "").trim();
  const name = String(formData.get("name") ?? "").trim();

  if (!workspaceId || !name) {
    return {
      status: "error",
      message: "Choose a workspace and enter a key name."
    };
  }

  try {
    const result = await createApiKey({ workspace_id: workspaceId, name });
    revalidatePath("/settings");
    return {
      status: "created",
      apiKey: result.api_key,
      record: result.record,
      message: "API key created. Copy it now; AgentGuard will not show it again."
    };
  } catch (error) {
    return {
      status: "error",
      message: messageFromError(error, "API key could not be created")
    };
  }
}
