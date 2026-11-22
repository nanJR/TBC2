"use client";
// Wraps a portal page. If login is on (Supabase is configured):
// - not signed in → go to /login
// - signed in with the other portal's role → go to your own portal
// - otherwise show the page, and share who is signed in (useMe) with the header.
// The real security check happens in the back end on every request; this is for comfort.

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

export function AuthGate({ role, children }: { role: "practitioner" | "asha"; children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return; // login is off
    supabase.auth
      .getSession()
      .then(async ({ data }) => {
        if (!data.session) {
          router.replace("/login");
          return;
        }
        const who = await getMe();
        if (who.role && who.role !== role && who.role !== "coordinator") {
          router.replace(HOME_FOR_ROLE[who.role]);
          return;
        }
        setMe(who);
      })
      .catch(() => setProblem("Could not check your login. Is the back end running?"));
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
