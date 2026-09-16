import { NextResponse } from "next/server";

import { formValue, messageFromError, sessionFromTokenPair } from "@/lib/auth-form";
import { loginAccount } from "@/lib/api";
import { setSession } from "@/lib/session";

function authRedirect(request: Request, path: string) {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const protocol = request.headers.get("x-forwarded-proto") ?? "https";
  const origin = host ? `${protocol}://${host}` : request.url;
  return NextResponse.redirect(new URL(path, origin));
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const email = formValue(formData, "email");
  const password = formValue(formData, "password");
  const workspaceSlug = formValue(formData, "workspace_slug");

  if (!email || !password) {
    return authRedirect(request, "/auth?mode=login&error=Email%20and%20password%20are%20required");
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
    return authRedirect(request, `/auth?mode=login&error=${message}`);
  }

  return authRedirect(request, "/");
}
