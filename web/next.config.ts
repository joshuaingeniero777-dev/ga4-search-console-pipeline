import type { NextConfig } from "next";

// Where the pipeline's API (api/ in this repo) is running. Read on the server
// only, so the browser never needs to know it.
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // The panel's pages call /backend/..., which Next.js forwards to the API.
  // The browser only ever talks to the panel itself, never to Google (CLAUDE.md rule 6).
  // Sign-in goes through here too (/backend/auth/...), so the API's session cookie
  // belongs to the panel's own address (docs/decisions.md, decision 19).
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
