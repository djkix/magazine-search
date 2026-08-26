import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("session");

  if (PUBLIC_PATHS.includes(pathname)) {
    if (hasSession) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // /api/* is proxied straight to the backend (see next.config.js rewrites)
  // and has its own auth via the session cookie/JWT - this middleware's
  // page-level redirect logic must never intercept it.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
