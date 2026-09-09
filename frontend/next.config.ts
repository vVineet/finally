import type { NextConfig } from "next";

// PLAN §11 / §13.D: the production artifact is a static export served by
// FastAPI from a single origin, so no CORS handling is needed there.
// `rewrites()` below only takes effect under `next dev` (the Next.js dev
// server proxying to the backend on :8000); Next.js ignores `rewrites()`
// for `output: 'export'` builds and will print a build-time notice about
// it, which is expected -- see PLAN §13.B8 and FRONTEND_SUMMARY.md.
const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  // Single-page app (one real route). No trailing-slash requirement from
  // FastAPI's static/SPA-fallback mount, so keep default clean URLs.
  // See FRONTEND_SUMMARY.md for the recorded rationale.
  trailingSlash: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
