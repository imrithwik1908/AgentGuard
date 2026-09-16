import { ApiRequestError } from "./api";
import type { AuthTokenPair } from "./types";

export function formValue(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

export function messageFromError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const details = error.details as Record<string, unknown> | null;

    if (typeof details?.message === "string") return details.message;

    if (Array.isArray(details?.detail)) {
      const first = details.detail[0] as { msg?: unknown; loc?: unknown[] } | undefined;
      if (typeof first?.msg === "string") {
        const field = Array.isArray(first.loc) ? first.loc.at(-1) : null;
        return typeof field === "string" ? `${field}: ${first.msg}` : first.msg;
      }
    }

    if (typeof details?.detail === "string") return details.detail;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

export function sessionFromTokenPair(result: AuthTokenPair) {
  return {
    accessToken: result.access_token,
    refreshToken: result.refresh_token,
    expiresAt: result.expires_at,
    refreshExpiresAt: result.refresh_expires_at,
    user: result.user,
    workspace: result.workspace
  };
}
