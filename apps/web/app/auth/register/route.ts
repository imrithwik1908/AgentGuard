import { NextResponse } from "next/server";

import { registerAccount } from "@/lib/api";
import { formValue, messageFromError, sessionFromTokenPair } from "@/lib/auth-form";
import { setSession } from "@/lib/session";

function authRedirect(request: Request, path: string) {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const protocol = request.headers.get("x-forwarded-proto") ?? "https";
  const origin = host ? `${protocol}://${host}` : request.url;
  return NextResponse.redirect(new URL(path, origin));
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const workspaceName = formValue(formData, "workspace_name");
  const workspaceSlug = formValue(formData, "workspace_slug");
  const email = formValue(formData, "email");
  const name = formValue(formData, "name");
  const password = formValue(formData, "password");

  if (!workspaceName || !workspaceSlug || !email || !name || !password) {
    return authRedirect(
      request,
      "/auth?mode=register&error=All%20fields%20are%20required%20to%20create%20a%20workspace"
    );
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
    return authRedirect(request, `/auth?mode=register&error=${message}`);
  }

  return authRedirect(request, "/");
}
