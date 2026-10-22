// Typed calls to the TBC² back end (services/api).
// Every page should go through these helpers instead of calling fetch() directly,
// so the back end address and response shapes live in one place.

// NEXT_PUBLIC_ variables are readable in the browser. Set it in .env.local
// (copy .env.example). Falls back to the local FastAPI server.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Mirrors ScreenResult in services/api/app/routers/screen.py.
// If you change one, change the other.
export type ScreenResult = {
  cough_score: number;
  xray_score: number | null;
  risk_score: number;
  is_mock: boolean;
};

/** Returns true if the back end answers /health with status "ok". */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!res.ok) return false;
    const body: { status: string } = await res.json();
    return body.status === "ok";
  } catch {
    // Network error: the back end is not running or not reachable.
    return false;
  }
}

/** Gets a fake screening result. Will be replaced by real cough/X-ray upload. */
export async function screenMock(): Promise<ScreenResult> {
  const res = await fetch(`${API_URL}/screen/mock`, { method: "POST" });
  if (!res.ok) throw new Error(`Screening failed: ${res.status}`);
  return res.json();
}
