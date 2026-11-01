// Typed calls to the TBC² back end (services/api).
// Every page should go through these helpers instead of calling fetch() directly,
// so the back end address and response shapes live in one place.

// NEXT_PUBLIC_ variables are readable in the browser. Set it in .env.local
// (copy .env.example). Falls back to the local FastAPI server.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Mirrors services/api/app/routers/screen.py and app/inference/referral.py.
// If you change one, change the other.
export type Symptom =
  | "cough_over_2_weeks"
  | "cough_under_2_weeks"
  | "fever"
  | "night_sweats"
  | "coughing_blood"
  | "chest_pain"
  | "shortness_of_breath"
  | "weight_loss"
  | "loss_of_appetite"
  | "fatigue"
  | "lymph_node_swelling";

export type Vulnerability =
  | "over_60"
  | "underweight"
  | "diabetes"
  | "hiv"
  | "smoker"
  | "alcohol_use"
  | "past_tb"
  | "household_contact";

export type ModelScore = {
  score: number;
  flagged: boolean;
  counts_towards_referral: boolean;
  status: string;
  note: string;
  version: string;
};

export type ScreenResult = {
  next_step: "naat" | "offer_xray" | "routine_care";
  reasons: string[];
  cough: ModelScore | null;
  xray: ModelScore | null;
  xray_heatmap_png: string | null;
  risk_score: number | null;
  notes: string[];
  is_mock: boolean;
};

export type ScreenRequest = {
  age: number;
  symptoms: Symptom[];
  vulnerabilities: Vulnerability[];
  imageSource: "digital" | "phone_photo";
  cough: Blob | null; // a WAV file
  xray: File | null;
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

/** Sends one person's answers and recordings. The server keeps none of the files. */
export async function screen(request: ScreenRequest): Promise<ScreenResult> {
  const form = new FormData();
  form.append("age", String(request.age));
  form.append("image_source", request.imageSource);
  request.symptoms.forEach((s) => form.append("symptoms", s));
  request.vulnerabilities.forEach((v) => form.append("vulnerabilities", v));
  if (request.cough) form.append("cough", request.cough, "cough.wav");
  if (request.xray) form.append("xray", request.xray);

  const res = await fetch(`${API_URL}/screen`, { method: "POST", body: form });
  if (!res.ok) {
    const body: { detail?: unknown } = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Screening failed.");
  }
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
