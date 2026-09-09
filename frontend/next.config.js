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
    // le backend, que les en-têtes de sécurité doivent être posés.
    // Volontairement sans Content-Security-Policy pour l'instant : le viewer
    // pdf.js utilise des workers et du blob:, une CSP mal calibrée casserait
    // la lecture des PDF. À ajouter séparément, après test sur le viewer.
    return [
      {
        source: "/:path*",
        headers: [
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
