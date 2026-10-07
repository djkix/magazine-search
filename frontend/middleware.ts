import { NextRequest, NextResponse } from "next/server";

// /login redirige un utilisateur deja connecte vers / : rester sur l'ecran
// de connexion une fois authentifie n'aurait aucun sens.
const PUBLIC_REDIRECT_IF_AUTHENTICATED = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("session");

  // Lien de partage : accessible sans compte, et un utilisateur deja
  // connecte doit pouvoir l'ouvrir normalement — pas de redirection vers /
  // comme pour /login, ce serait une vraie regression pour quelqu'un qui
  // recoit son propre lien alors qu'il est connecte sur un autre onglet.
  if (pathname.startsWith("/partage/")) {
    return NextResponse.next();
  }

  if (PUBLIC_REDIRECT_IF_AUTHENTICATED.includes(pathname)) {
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
