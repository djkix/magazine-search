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
};

module.exports = nextConfig;
