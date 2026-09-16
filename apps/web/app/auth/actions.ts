"use server";

import { redirect } from "next/navigation";

import { ApiRequestError, loginAccount, logoutAccount, registerAccount } from "@/lib/api";
import { clearSession, setSession } from "@/lib/session";

function formValue(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function messageFromError(error: unknown, fallback: string): string {
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

function sessionFromTokenPair(result: Awaited<ReturnType<typeof loginAccount>>) {
  return {
    accessToken: result.access_token,
    refreshToken: result.refresh_token,
    expiresAt: result.expires_at,
    refreshExpiresAt: result.refresh_expires_at,
    user: result.user,
    workspace: result.workspace
  };
}

export async function loginAction(formData: FormData) {
  const email = formValue(formData, "email");
  const password = formValue(formData, "password");
  const workspaceSlug = formValue(formData, "workspace_slug");

  if (!email || !password) {
    redirect("/auth?mode=login&error=Email%20and%20password%20are%20required");
  }

  try {
    const result = await loginAccount({
      email,
      password,
      workspace_slug: workspaceSlug || undefined
    });
    await setSession(sessionFromTokenPair(result));
  } catch (error) {
    const message = encodeURIComponent(messageFromError(error, "Sign in failed"));
    redirect(`/auth?mode=login&error=${message}`);
  }
  redirect("/");
}

export async function registerAction(formData: FormData) {
  const workspaceName = formValue(formData, "workspace_name");
  const workspaceSlug = formValue(formData, "workspace_slug");
  const email = formValue(formData, "email");
  const name = formValue(formData, "name");
  const password = formValue(formData, "password");

  if (!workspaceName || !workspaceSlug || !email || !name || !password) {
    redirect("/auth?mode=register&error=All%20fields%20are%20required%20to%20create%20a%20workspace");
  }

  try {
    const result = await registerAccount({
      workspace_name: workspaceName,
      workspace_slug: workspaceSlug,
      email,
      name,
      password
    });
    await setSession(sessionFromTokenPair(result));
  } catch (error) {
    const message = encodeURIComponent(messageFromError(error, "Workspace could not be created"));
    redirect(`/auth?mode=register&error=${message}`);
  }
  redirect("/");
}

export async function logoutAction() {
  try {
    await logoutAccount();
  } catch {
    // Local session cleanup still wins if the API is unavailable.
  }
  await clearSession();
  redirect("/auth?mode=login");
}
