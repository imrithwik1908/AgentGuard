import "server-only";

import { cookies } from "next/headers";

export interface WebSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
  refreshExpiresAt: string;
  user: {
    id: string;
    workspace_id: string;
    email: string;
    name: string;
    role: string;
    created_at: string;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    created_at: string;
  };
}

const SESSION_COOKIE = "agentguard_session";

export async function getSession(): Promise<WebSession | null> {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value) return null;
  try {
    return JSON.parse(value) as WebSession;
  } catch {
    return null;
  }
}

export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  return session?.accessToken ?? null;
}

export async function setSession(session: WebSession): Promise<void> {
  const expires = new Date(session.refreshExpiresAt);
  (await cookies()).set(SESSION_COOKIE, JSON.stringify(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires
  });
}

export async function clearSession(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}
