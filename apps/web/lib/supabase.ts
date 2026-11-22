// The Supabase client in the browser. It is only used to sign in and out: all data
// still goes through the FastAPI back end (lib/api.ts), which checks the login token.
//
// Both values are public by design: the publishable key can't read any table (row-level
// security blocks it), it only lets people sign in. If they aren't set, login is off and
// the portals work without it (the back end must then run without a secret key too).

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null;

/** The current access token, to send to the back end, or null if not signed in. */
export async function accessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
