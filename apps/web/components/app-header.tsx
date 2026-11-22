"use client";
// The top bar on every portal page, as in the Figma: the TBC² mark on the left, the two
// portals as a segmented switch in the middle, and the theme switch and who is signed
// in on the right.

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoMark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const PORTALS = [
  { href: "/counter", label: "Counter" },
  { href: "/asha", label: "ASHA Portal" },
];

export function AppHeader({ who }: { who: string }) {
  const pathname = usePathname();
  return (
    <header className="bg-card/90 border-t-primary sticky top-0 z-10 border-t-4 border-b backdrop-blur print:hidden">
      <div className="mx-auto flex h-[4.5rem] max-w-[1440px] items-center gap-4 px-4 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="TBC² Home">
          <LogoMark className="h-12" />
          <span className="hidden border-l pl-3 text-xl font-bold tracking-tight md:inline">
            TB Care Coordinator
          </span>
        </Link>

        <nav className="bg-secondary mx-auto flex rounded-full p-1" aria-label="Portals">
          {PORTALS.map((portal) => {
            const active = pathname.startsWith(portal.href);
            return (
              <Link
                key={portal.href}
                href={portal.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-full px-3 py-1.5 text-sm transition-colors sm:px-5",
                  active
                    ? "bg-card text-primary font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {portal.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <span className="text-muted-foreground hidden text-sm lg:inline">{who}</span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
