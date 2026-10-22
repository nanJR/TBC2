import type { MetadataRoute } from "next";

// The web app manifest lets phones "install" TBC² to the home screen (PWA).
// Next.js serves this at /manifest.webmanifest automatically.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TBC² — TB care coordinator",
    short_name: "TBC²",
    description: "Screen for TB and follow up on patients at risk of stopping treatment.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0e6b66",
    icons: [{ src: "/favicon.ico", sizes: "any", type: "image/x-icon" }],
  };
}
