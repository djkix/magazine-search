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
  // et a sa propre auth via le cookie de session / JWT - cette redirection
  // ne doit jamais l'intercepter. Un chemin avec une extension (manifest,
  // icônes, pdf.worker.min.mjs...) est un fichier statique de /public, pas
  // une page : aucune de nos pages n'a de point dans son chemin, donc ce
  // filtre couvre tout fichier public présent ou futur sans liste au cas
  // par cas (bug vécu : pdf.worker.min.mjs redirigé vers /login pour un
  // visiteur non connecté, cassant la lecture via un lien de partage).
  matcher: ["/((?!api|_next/static|_next/image|.*\\..*).*)"],
};
