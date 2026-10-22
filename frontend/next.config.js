// Content-Security-Policy. Contraintes prises en compte :
// - Next.js injecte des scripts inline (amorçage, données RSC) : sans
//   nonces par requête, ce qui rendrait toutes les pages dynamiques,
//   'unsafe-inline' est nécessaire dans script-src. Le gain reste réel :
//   aucun script d'une origine tierce non listée, ni eval, ni plugin.
// - pdf.js : worker servi par /pdf.worker.min.mjs (même origine) ; blob:
//   autorisé dans worker-src et img-src pour ses chemins de repli. Les
//   polices des PDF sont chargées via l'API FontFace (data: en repli).
// - Google Identity Services (bouton « Se connecter avec Google ») : script,
//   iframe, styles et appels sous https://accounts.google.com/gsi/, selon la
//   documentation de Google.
// - Icônes Material Symbols : feuille sur fonts.googleapis.com, fichiers de
//   police sur fonts.gstatic.com. Les autres polices (next/font) sont
//   auto-hébergées.
// - En développement, React a besoin d'eval pour ses outils de débogage.
const GSI = "https://accounts.google.com/gsi/";
const estDev = process.env.NODE_ENV !== "production";
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${estDev ? " 'unsafe-eval'" : ""} ${GSI}client`,
  `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com ${GSI}style`,
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' data: blob:",
  `connect-src 'self' ${GSI}`,
  `frame-src ${GSI}`,
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    // Proxy /api/* to the backend container over the internal Docker
    // network, so the browser only ever talks to this single origin.
    // The reverse proxy in front of the app then needs just one plain
    // forward to this port — no path-based routing to a second port.
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_INTERNAL_URL || "http://app-backend:8000"}/api/:path*`,
      },
    ];
  },
  async headers() {
    // Le navigateur ne parle qu'à cette origine : c'est donc ici, et non sur
    // le backend, que les en-têtes de sécurité doivent être posés. La CSP
    // (voir en tête de fichier) a été validée sur le viewer pdf.js.
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: CSP },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
