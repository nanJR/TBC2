// Typed calls to the TBC² back end (services/api).
// Every page should go through these helpers instead of calling fetch() directly,
// so the back end address and response shapes live in one place.
//
// The types below mirror services/api/app/schemas.py and ScreenResult in
// app/routers/screen.py by hand. If you change one side, change the other.

import { accessToken } from "@/lib/supabase";

// NEXT_PUBLIC_ variables are readable in the browser. Set it in .env.local
// (copy .env.example). Falls back to the local FastAPI server.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- Shared words (app/inference/referral.py and scoring.py) ----

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

export type NextStep = "naat" | "offer_xray" | "routine_care";
export type RiskBand = "low" | "moderate" | "high";
export type Sex = "M" | "F";

export type ModelScore = {
  score: number;
  flagged: boolean;
  counts_towards_referral: boolean;
  status: string;
  note: string;
  version: string;
};

// ---- Counter: /screen, /abha/lookup, /screenings ----

export type ScreenResult = {
  screening_id: string;
  next_step: NextStep;
  reasons: string[];
  cough: ModelScore | null;
  xray: ModelScore | null;
  xray_heatmap_png: string | null;
  risk_score: number | null; // 0-1, the threshold sits at 0.5
  risk_band: RiskBand | null;
  notes: string[];
  is_mock: boolean;
};

export type ScreenRequest = {
  age: number;
  sex: Sex;
  district: string;
  hasPhone: boolean;
  abhaLinked: boolean;
  symptoms: Symptom[];
  vulnerabilities: Vulnerability[];
  cough: Blob | null; // a WAV file
};

export type AbhaRecord = {
  abha_last4: string;
  age: number;
  sex: Sex;
  district: string;
  history: Vulnerability[];
  conditions: string[];
  is_mock: boolean;
};

export type DismissReason =
  | "declined"
  | "already_on_treatment"
  | "referred_elsewhere"
  | "low_risk"
  | "other";

export type Screening = {
  screening_id: string;
  screened_at: string; // ISO date-time
  practitioner: string;
  age: number;
  sex: Sex;
  district: string;
  has_phone: boolean;
  symptoms: Symptom[];
  history: Vulnerability[];
  abha_linked: boolean;
  cough_risk: number | null;
  risk_band: RiskBand | null;
  recommended_action: NextStep;
  reasons: string[];
  decision: "pending" | "forwarded" | "dismissed";
  dismiss_reason: DismissReason | null;
  case_id: string | null;
  is_mock: boolean;
};

// ---- ASHA: /cases, /van-slots, /overview ----

export type CaseStatus =
  | "new"
  | "contacted"
  | "xray_booked"
  | "xray_done"
  | "risk_combined"
  | "naat_positive"
  | "on_treatment"
  | "closed";

export type NaatResult =
  | "mtb_detected_rr_not_detected"
  | "mtb_detected_rr_detected"
  | "mtb_not_detected"
  | "inconclusive";

export type WeightBand = "25-34" | "35-49" | "50-64" | "65-75" | "over-75";

export type VanSlot = {
  slot_id: string;
  district: string;
  site: string;
  day: string; // "YYYY-MM-DD"
  capacity: number;
  booked: number;
};

export type Case = {
  case_id: string;
  screening_id: string;
  forwarded_at: string;
  practitioner: string;
  age: number;
  sex: Sex;
  district: string;
  has_phone: boolean;
  symptoms: Symptom[];
  history: Vulnerability[];
  abha_linked: boolean;
  cough_risk: number | null;
  counter_action: NextStep;
  counter_reasons: string[];
  asha_name: string;
  status: CaseStatus;
  contact_due_at: string;
  contact_attempts: number;
  contacted_at: string | null;
  sputum_collected_at: string | null;
  xray_slot: VanSlot | null;
  xray_source: "upload" | "van_reading" | null;
  xray_risk: number | null;
  van_reading: "normal" | "abnormal" | null;
  combined_risk: number | null;
  combined_band: RiskBand | null;
  combined_action: NextStep | null;
  combined_reasons: string[];
  naat_result: NaatResult | null;
  naat_attempts: number;
  mo_name: string | null;
  nikshay_id: string | null;
  notified_in_nikshay: boolean;
  patient_id: string | null;
  closed_reason: string | null;
  is_mock: boolean;
};

export type StartTreatment = {
  mo_name: string;
  phc: string;
  weight_band: WeightBand;
  nikshay_id?: string;
  notified_in_nikshay: boolean;
};

export type Overview = {
  screened: number;
  forwarded: number;
  tested: number;
  on_treatment: number;
  awaiting_contact: number;
  overdue: number;
  is_mock: boolean;
};

// ---- Treatment tracking: /patients, /risk, /actions ----

export type DoseDay = "taken" | "missed";

// IsoScreen: a urine strip that shows whether isoniazid was taken in the last 1-2 days.
export type IsoScreenTest = {
  day_on_treatment: number;
  result: "inh_detected" | "inh_not_detected" | "indeterminate";
  hours_since_dose: number | null;
};

export type Patient = {
  patient_id: string;
  age: number;
  sex: Sex;
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
  dose_log_last_28_days: DoseDay[]; // oldest first
  last_dose_logged_on: string | null;
  missed_in_a_row: number;
  isoscreen_tests: IsoScreenTest[];
  side_effect_reported: boolean;
  asha_name: string | null;
  phc: string | null;
  weight_band: WeightBand | null;
  case_id: string | null;
};

// Missed-dose ladder: call after 3 missed days in a row, ASHA visit after 7.
export type LadderStep = "on_track" | "call" | "asha_visit";

export type RiskEntry = {
  patient: Patient;
  risk_score: number;
  reasons: string[];
  ladder_step: LadderStep;
  isoscreen_every_days: number | null; // null when the regimen has no isoniazid
  is_mock: boolean;
};

export type Action = {
  action_id: number;
  patient_id: string;
  type: "call" | "asha_visit" | "isoscreen_test" | "side_effect_referral";
  reason: string;
  draft: string;
  status: "pending" | "approved" | "rejected";
};

// ---- Helpers ----

export type Me = {
  signed_in: boolean;
  email: string | null;
  role: "practitioner" | "asha" | "coordinator" | null;
  full_name: string | null;
  district: string | null;
  place: string | null;
};

/** Adds the signed-in user's token, so the back end knows who is asking. */
async function authHeaders(): Promise<Record<string, string>> {
  const token = await accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Every request goes through here, with the login token added. Signed-out users are
 * sent to /login by components/auth-gate.tsx, and Supabase refreshes tokens itself. */
async function call(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: { ...(init.headers as Record<string, string>), ...(await authHeaders()) },
  });
}

/** Turn an error response into a readable message (FastAPI puts it in "detail"). */
async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body: { detail?: unknown } = await res.json().catch(() => ({}));
  return typeof body.detail === "string" ? body.detail : fallback;
}

// Small helper so every JSON call handles errors the same way.
async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await call(path, init);
  if (!res.ok) throw new Error(await errorMessage(res, `${path} failed: ${res.status}`));
  return res.json();
}

const postJson = <T>(path: string, body?: unknown) =>
  getJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

/** Returns true if the back end answers /health with status "ok". */
export async function checkHealth(): Promise<boolean> {
  try {
    // Give up on one try after 10 s; the caller tries again while the API wakes up.
    const res = await fetch(`${API_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) return false;
    const body: { status: string } = await res.json();
    return body.status === "ok";
  } catch {
    // Network error: the back end is not running or not reachable.
    return false;
  }
}

// ---- Counter ----

/** Sends one person's answers and cough. The server keeps the answers, never the file. */
export async function screen(request: ScreenRequest): Promise<ScreenResult> {
  const form = new FormData();
  form.append("age", String(request.age));
  form.append("sex", request.sex);
  form.append("district", request.district);
  form.append("has_phone", String(request.hasPhone));
  form.append("abha_linked", String(request.abhaLinked));
  request.symptoms.forEach((s) => form.append("symptoms", s));
  request.vulnerabilities.forEach((v) => form.append("vulnerabilities", v));
  if (request.cough) form.append("cough", request.cough, "cough.wav");

  const res = await call("/screen", { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res, "Screening failed."));
  return res.json();
}

export const lookupAbha = (abhaNumber: string, consent: boolean) =>
  postJson<AbhaRecord>("/abha/lookup", { abha_number: abhaNumber, consent });

export const getScreenings = (limit = 20) => getJson<Screening[]>(`/screenings?limit=${limit}`);

export const forwardScreening = (id: string, consentContact: boolean) =>
  postJson<Case>(`/screenings/${id}/forward`, { consent_contact: consentContact });

export const dismissScreening = (id: string, reason: DismissReason) =>
  postJson<Screening>(`/screenings/${id}/dismiss`, { reason });

export const getDistricts = () => getJson<string[]>("/districts");

/** Who is signed in, with their role. signed_in is false when login is turned off. */
export const getMe = () => getJson<Me>("/me");

// ---- ASHA ----

const inDistrict = (district?: string) =>
  district ? `?district=${encodeURIComponent(district)}` : "";

export const getOverview = (district?: string) =>
  getJson<Overview>(`/overview${inDistrict(district)}`);

export const getCases = (district?: string) => getJson<Case[]>(`/cases${inDistrict(district)}`);

export const getVanSlots = (district?: string) =>
  getJson<VanSlot[]>(`/van-slots${inDistrict(district)}`);

export const recordContact = (id: string, reached: boolean) =>
  postJson<Case>(`/cases/${id}/contact`, { reached });

export const recordSputum = (id: string) => postJson<Case>(`/cases/${id}/sputum`);

export const bookVan = (id: string, slotId: string) =>
  postJson<Case>(`/cases/${id}/schedule`, { slot_id: slotId });

/** Uploads the X-ray from the van. It is scored in memory and never stored. */
export async function uploadCaseXray(id: string, xray: File): Promise<Case> {
  const form = new FormData();
  form.append("xray", xray);
  const res = await call(`/cases/${id}/xray`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res, "X-ray upload failed."));
  return res.json();
}

export const recordVanReading = (id: string, reading: "normal" | "abnormal") =>
  postJson<Case>(`/cases/${id}/van-reading`, { reading });

export const combineRisk = (id: string) => postJson<Case>(`/cases/${id}/combine`);

export const recordNaat = (id: string, result: NaatResult) =>
  postJson<Case>(`/cases/${id}/naat`, { result });

export const startTreatment = (id: string, form: StartTreatment) =>
  postJson<Case>(`/cases/${id}/start-treatment`, form);

export const closeCase = (
  id: string,
  reason: "xray_clear" | "not_reached" | "moved_away" | "declined" | "other",
) => postJson<Case>(`/cases/${id}/close`, { reason });

// ---- Tracking ----

export const getWeeklyRisk = (limit = 20, district?: string) =>
  getJson<RiskEntry[]>(
    `/risk/weekly?limit=${limit}${district ? `&district=${encodeURIComponent(district)}` : ""}`,
  );

export const recordDose = (patientId: string, status: DoseDay) =>
  postJson<RiskEntry>(`/patients/${patientId}/doses`, { status });

export const recordIsoScreen = (
  patientId: string,
  result: IsoScreenTest["result"],
  hoursSinceDose?: number,
) =>
  postJson<RiskEntry>(`/patients/${patientId}/isoscreen`, {
    result,
    hours_since_dose: hoursSinceDose ?? null,
  });

export const getActions = () => getJson<Action[]>("/actions");

export const decideAction = (id: number, decision: "approve" | "reject") =>
  postJson<Action>(`/actions/${id}/${decision}`);
