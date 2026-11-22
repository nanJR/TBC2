import type { NextConfig } from "next";

// On the deployed site the API lives on another domain (Render). Ad and tracker blockers
// often block a page's requests to other domains, so the browser calls /api/... on the
// website's own domain instead, and Vercel forwards them to the API. See lib/api.ts.
// Locally (http://localhost:8000) the browser calls the API directly.
const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const proxyApi = API.startsWith("https://");

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // `next dev` and `next build` warn when this Next.js version has a published
    // security advisory. "security" is the default; we set it so it is easy to see.
    agentUpgrade: "security",
  },
  // Old addresses from earlier versions still work: the counter check moved to
  // /counter and the district dashboard became the ASHA portal.
  rewrites() {
    return proxyApi ? [{ source: "/api/:path*", destination: `${API}/:path*` }] : [];
  },
  redirects() {
    return [
      { source: "/screen", destination: "/counter", permanent: false },
      { source: "/dashboard", destination: "/asha", permanent: false },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
