import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

// Inter: a clean, highly readable sans-serif (also used in the Figma design).
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TBC² · TB Care Coordinator",
  description: "TB Care Coordinator: counter screening, ASHA follow-up and treatment tracking",
};

// Runs before the page paints, so a dark-mode user never sees a white flash.
// Uses the saved choice if there is one, otherwise the device's setting.
const setTheme = `try {
  var saved = localStorage.getItem("theme");
  var dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  if (dark) document.documentElement.classList.add("dark");
} catch (e) {}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the script above may add "dark" before React loads.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: setTheme }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
