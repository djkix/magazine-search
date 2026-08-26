/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  webpack: (config) => {
    // pdfjs-dist ships its worker as a raw ESM file. Next bundles it as a
    // static asset via `new URL(...)`, but Terser still tries to minify it
    // and chokes on top-level import/export syntax. Skip minification for
    // that one file instead.
    for (const minimizer of config.optimization.minimizer ?? []) {
      if (minimizer.constructor.name === "TerserPlugin") {
        minimizer.options.exclude = /pdf\.worker/;
      }
    }
    return config;
  },
};

module.exports = nextConfig;
