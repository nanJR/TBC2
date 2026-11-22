import type { NextConfig } from "next";

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
