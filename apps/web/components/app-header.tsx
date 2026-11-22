"use client";
// The top bar on every portal page, as in the Figma: the TBC² mark on the left, the two
// portals as a segmented switch in the middle, and the theme switch and who is signed
// in on the right.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { useMe } from "@/components/auth-gate";
import { LogoMark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { supabase } from "@/lib/supabase";
import { cn } from "@/lib/utils";

const PORTALS = [
  { href: "/counter", label: "Counter" },
  { href: "/asha", label: "ASHA Portal" },
];

export function AppHeader({ who }: { who: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const me = useMe();
  // When signed in, show the real account instead of the page's default label.
  const label = me?.signed_in
    ? `${me.role === "asha" ? "ASHA " : ""}${me.full_name ?? ""}${me.place ? ` · ${me.place}` : ""}`
    : who;

  async function signOut() {
    await supabase?.auth.signOut();
    router.replace("/login");
  }

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
          <span className="text-muted-foreground hidden text-sm lg:inline">{label}</span>
          <ThemeToggle />
          {me?.signed_in && (
            <button
              type="button"
              onClick={signOut}
              aria-label="Sign Out"
              title="Sign Out"
              className="hover:bg-secondary text-muted-foreground hover:text-foreground grid size-9 place-items-center rounded-full border transition-colors"
            >
              <LogOut className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
