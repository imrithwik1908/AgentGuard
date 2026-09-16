import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "agentguard_session";
const PROTECTED_PREFIXES = [
  "/",
  "/datasets",
  "/evaluations",
  "/projects",
  "/releases",
  "/settings",
  "/traces"
];
const PUBLIC_PREFIXES = ["/auth", "/docs", "/guide", "/tutorial"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (isPublic) return NextResponse.next();

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (!isProtected || request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/auth";
  url.searchParams.set("mode", "login");
  url.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/",
    "/datasets/:path*",
    "/evaluations/:path*",
    "/projects/:path*",
    "/releases/:path*",
    "/settings/:path*",
    "/traces/:path*"
  ]
};
