"use client";
// Sign-in page (Supabase Auth, email and password). After signing in, each role goes
// to its own portal: pharmacists to /counter, ASHAs to /asha.

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, LogIn } from "lucide-react";

import { AppFooter } from "@/components/app-footer";
import { HOME_FOR_ROLE } from "@/components/auth-gate";
import { LogoMark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { getMe } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const field = "bg-card rounded-lg border px-3 py-2.5 text-sm outline-none focus:border-primary";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.signInWithPassword({ email, password });
    if (failed) {
      setError("Wrong email or password.");
      setBusy(false);
      return;
    }
    try {
      const me = await getMe();
      router.replace(HOME_FOR_ROLE[me.role ?? "practitioner"] ?? "/");
    } catch {
      setError("Signed in, but your account has no TBC² role yet.");
      setBusy(false);
    }
  }

  return (
    <>
      {/* Back to the home page, styled like the round buttons in the header. */}
      <Link
        href="/"
        className="bg-card hover:bg-secondary text-muted-foreground hover:text-foreground absolute top-4 left-4 inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition-colors"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Back
      </Link>
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <main className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="bg-card flex w-full max-w-sm flex-col gap-6 rounded-2xl border p-8">
          <div className="flex flex-col items-center gap-2 text-center">
            <LogoMark className="h-20" />
            <h1 className="text-2xl font-bold tracking-tight">Sign In to TBC²</h1>
            <p className="text-muted-foreground text-sm">TB Care Coordinator</p>
          </div>

          {supabase ? (
            <form onSubmit={signIn} className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-xs font-medium">
                Email
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={field}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium">
                Password
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={field}
                />
              </label>
              {error && <p className="text-destructive text-sm">{error}</p>}
              <Button size="lg" type="submit" disabled={busy}>
                <LogIn aria-hidden /> {busy ? "Signing In…" : "Sign In"}
              </Button>
            </form>
          ) : (
            <p className="text-muted-foreground text-center text-sm">
              Login is turned off on this computer.{" "}
              <Link href="/" className="text-primary underline">
                Open the portals
              </Link>
            </p>
          )}
        </div>
      </main>
      <AppFooter />
    </>
  );
}
