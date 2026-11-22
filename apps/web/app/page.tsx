import Link from "next/link";
import { ArrowRight, Store, UserRound } from "lucide-react";

import { AppFooter } from "@/components/app-footer";
import { BackendStatus } from "@/components/backend-status";
import { LogoMark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";

// Home page: pick a portal. The counter portal is for pharmacists and local
// practitioners; the ASHA portal is for the health worker who follows people up.
const PORTALS = [
  {
    href: "/counter",
    icon: Store,
    title: "Counter Portal",
    text: "Pharmacists and local practitioners: fetch ABHA history, mark symptoms, analyse a cough and forward people at risk to an ASHA.",
  },
  {
    href: "/asha",
    icon: UserRound,
    title: "ASHA Portal",
    text: "ASHA workers: follow up forwarded cases, book the mobile X-ray van, combine risks, record NAAT results and track treatment every day.",
  },
];

export default function Home() {
  return (
    <>
      <div className="absolute top-4 right-4 flex items-center gap-3">
        <BackendStatus />
        <ThemeToggle />
      </div>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col justify-center gap-10 px-4 py-16">
        <header className="flex flex-col items-center gap-3 text-center">
          <h1>
            <LogoMark className="h-40" />
          </h1>
          <p className="text-3xl font-bold tracking-tight">TB Care Coordinator</p>
          <p className="text-muted-foreground max-w-xl">
            Screen at the counter, follow up in the community, and help people finish
            treatment.
          </p>
        </header>

        <div className="grid gap-4 sm:grid-cols-2">
          {PORTALS.map((p) => (
            <Link
              key={p.href}
              href={p.href}
              className="bg-card hover:border-primary group flex flex-col gap-3 rounded-2xl border p-6 transition-colors"
            >
              <p.icon className="text-primary size-6" aria-hidden />
              <span className="text-lg font-semibold">{p.title}</span>
              <span className="text-muted-foreground text-sm">{p.text}</span>
              <span className="text-primary mt-auto inline-flex items-center gap-1 text-sm font-medium">
                Open <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>

      </main>
      <AppFooter />
    </>
  );
}
