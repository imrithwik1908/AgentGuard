"use server";

import { redirect } from "next/navigation";

import { loginAccount, logoutAccount, registerAccount } from "@/lib/api";
import { clearSession, setSession } from "@/lib/session";

function formValue(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
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
  try {
    const result = await loginAccount({
      email: formValue(formData, "email"),
      password: formValue(formData, "password"),
      workspace_slug: formValue(formData, "workspace_slug") || undefined
    });
    await setSession(sessionFromTokenPair(result));
  } catch (error) {
    const message = encodeURIComponent(error instanceof Error ? error.message : String(error));
    redirect(`/auth?mode=login&error=${message}`);
  }
  redirect("/");
}

export async function registerAction(formData: FormData) {
  try {
    const result = await registerAccount({
      workspace_name: formValue(formData, "workspace_name"),
      workspace_slug: formValue(formData, "workspace_slug"),
      email: formValue(formData, "email"),
      name: formValue(formData, "name"),
      password: formValue(formData, "password")
    });
    await setSession(sessionFromTokenPair(result));
  } catch (error) {
    const message = encodeURIComponent(error instanceof Error ? error.message : String(error));
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
