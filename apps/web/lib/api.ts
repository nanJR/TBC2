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

// ---- Patients, risk and actions: mirrors services/api/app/schemas.py ----

export type Patient = {
  patient_id: string;
  age: number;
  sex: "M" | "F";
  district: string;
  lat: number;
  lon: number;
  distance_to_clinic_km: number;
  regimen: "drug-sensitive" | "drug-resistant";
  days_on_treatment: number;
  doses_missed_last_4_weeks: number;
  alcohol_use: boolean;
  undernourished: boolean;
  previously_treated: boolean;
  has_phone: boolean;
  gets_nutrition_support: boolean;
};

export type RiskEntry = {
  patient: Patient;
  risk_score: number;
  reasons: string[];
  is_mock: boolean;
};

export type Action = {
  action_id: number;
  patient_id: string;
  type: "sms" | "home_visit" | "nutrition_support";
  draft: string;
  status: "pending" | "approved" | "rejected";
};

// Small helper so every call handles errors the same way.
async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const getWeeklyRisk = (limit = 20) =>
  getJson<RiskEntry[]>(`/risk/weekly?limit=${limit}`);

export const getActions = () => getJson<Action[]>("/actions");

export const decideAction = (id: number, decision: "approve" | "reject") =>
  getJson<Action>(`/actions/${id}/${decision}`, { method: "POST" });
