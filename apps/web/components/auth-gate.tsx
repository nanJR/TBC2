"use client";
// Wraps a portal page. If login is on (Supabase is configured):
// - not signed in → go to /login (or home, right after signing out)
// - signed in with the other portal's role → go to your own portal
// - otherwise show the page, and share who is signed in (useMe) with the header.
// The check runs again whenever the login changes, in this tab or another one (one
// browser shares one login across its tabs), so a page can't stay open for the wrong role.
// The real security check happens in the back end on every request.

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { getMe, type Me } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const MeContext = createContext<Me | null>(null);

/** The signed-in user, or null when login is off. */
export const useMe = () => useContext(MeContext);

export const HOME_FOR_ROLE: Record<string, string> = {
  practitioner: "/counter",
  asha: "/asha",
  coordinator: "/asha",
};

/** Which portals a role may open. The coordinator (admin) may open both. */
export const PORTALS_FOR_ROLE: Record<string, string[]> = {
  practitioner: ["/counter"],
  asha: ["/asha"],
  coordinator: ["/counter", "/asha"],
};

export function AuthGate({ role, children }: { role: "practitioner" | "asha"; children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const auth = supabase?.auth;
    if (!auth) return; // login is off
    let active = true;

    // signedOut: the user just signed out, so go home instead of to the sign-in page.
    async function check(signedOut = false) {
      try {
        const { data } = await auth!.getSession();
        if (!active) return;
        if (!data.session) {
          setMe(null);
          router.replace(signedOut ? "/" : "/login");
          return;
        }
        const who = await getMe();
        if (!active) return;
        if (who.role && who.role !== role && who.role !== "coordinator") {
          setMe(null); // hide this page at once, before moving
          router.replace(HOME_FOR_ROLE[who.role]);
          return;
        }
        setMe(who);
      } catch {
        if (active) setProblem("Could not check your login. Is the back end running?");
      }
    }

    check();
    // Signing in as someone else, or out, anywhere in this browser: check again.
    const { data: listener } = auth.onAuthStateChange((event) => {
      if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "USER_UPDATED") {
        setMe(null);
        check(event === "SIGNED_OUT");
      }
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [role, router]);

  if (!supabase) return <>{children}</>;
  if (!me) {
    return (
      <div className="text-muted-foreground grid flex-1 place-items-center text-sm">
        {problem ?? "Checking Your Login…"}
      </div>
    );
  }
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}
