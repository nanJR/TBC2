// Plain-language labels for the codes the API sends, shared by both portals.
// Wording aims at a qualified pharmacist or ASHA: precise, but not doctor-level.

import type {
  CaseStatus,
  DismissReason,
  NaatResult,
  NextStep,
  RiskBand,
  Symptom,
  Vulnerability,
  WeightBand,
} from "@/lib/api";

export const SYMPTOMS: { value: Symptom; label: string }[] = [
  { value: "cough_over_2_weeks", label: "Cough > 2 Weeks" },
  { value: "cough_under_2_weeks", label: "Cough < 2 Weeks" },
  { value: "fever", label: "Fever" },
  { value: "night_sweats", label: "Night Sweats" },
  { value: "coughing_blood", label: "Coughing Blood" },
  { value: "chest_pain", label: "Chest Pain" },
  { value: "shortness_of_breath", label: "Breathlessness" },
  { value: "weight_loss", label: "Weight Loss" },
  { value: "loss_of_appetite", label: "Loss of Appetite" },
  { value: "fatigue", label: "Fatigue" },
  { value: "lymph_node_swelling", label: "Swollen Neck Glands" },
];

// "over_60" is added by the server from the age, so it isn't offered as a choice.
export const HISTORY: { value: Vulnerability; label: string }[] = [
  { value: "diabetes", label: "Diabetes" },
  { value: "hiv", label: "HIV" },
  { value: "past_tb", label: "Past TB" },
  { value: "household_contact", label: "TB at Home" },
  { value: "underweight", label: "Underweight (BMI < 18.5)" },
  { value: "smoker", label: "Smoker" },
  { value: "alcohol_use", label: "Alcohol Use" },
];

export const SYMPTOM_LABEL = Object.fromEntries(SYMPTOMS.map((s) => [s.value, s.label]));
export const HISTORY_LABEL: Record<string, string> = {
  ...Object.fromEntries(HISTORY.map((h) => [h.value, h.label])),
  over_60: "Over 60",
};

export const ACTION: Record<NextStep, { title: string; detail: string }> = {
  naat: {
    title: "Refer for NAAT Test",
    detail: "Presumptive TB. The ASHA collects sputum and books the chest X-ray.",
  },
  offer_xray: {
    title: "Refer for Chest X-Ray",
    detail: "The ASHA books the mobile X-ray van to double-check.",
  },
  routine_care: {
    title: "No Referral Needed",
    detail: "Advise them to return if a cough lasts 2 weeks or other symptoms appear.",
  },
};

export const BAND: Record<RiskBand, { label: string; tone: Tone }> = {
  low: { label: "Low Risk", tone: "ok" },
  moderate: { label: "Moderate Risk", tone: "wait" },
  high: { label: "High Risk", tone: "alert" },
};

export const DISMISS_REASONS: { value: DismissReason; label: string }[] = [
  { value: "low_risk", label: "Low Risk, No Symptoms" },
  { value: "declined", label: "Person Declined" },
  { value: "already_on_treatment", label: "Already on TB Treatment" },
  { value: "referred_elsewhere", label: "Referred Elsewhere" },
  { value: "other", label: "Other" },
];

export const CASE_STATUS: Record<CaseStatus, string> = {
  new: "New",
  contacted: "Contacted",
  xray_booked: "X-Ray Booked",
  xray_done: "X-Ray Done",
  risk_combined: "Risk Combined",
  naat_positive: "TB Confirmed",
  on_treatment: "On Treatment",
  closed: "Closed",
};

export const NAAT: Record<NaatResult, string> = {
  mtb_detected_rr_not_detected: "MTB Detected, RR Not Detected",
  mtb_detected_rr_detected: "MTB Detected, RR Detected",
  mtb_not_detected: "MTB Not Detected",
  inconclusive: "Inconclusive (Repeat with New Sample)",
};

// Why a case was closed, as the server records it.
export const CLOSED_REASON: Record<string, string> = {
  "xray clear": "X-Ray Clear: No Signs of TB",
  "not reached": "Not Reached After Several Tries",
  "moved away": "Moved Away",
  declined: "Person Declined",
  other: "Closed for Another Reason",
  "NAAT: MTB not detected": "NAAT: MTB Not Detected",
};

export const WEIGHT_BANDS: WeightBand[] = ["25-34", "35-49", "50-64", "65-75", "over-75"];

export type Tone = "ok" | "wait" | "alert" | "neutral";

/** 0.6736 → "67%". */
export const percent = (value: number) => `${Math.round(value * 100)}%`;

/** "2026-11-24" → "Tue 24 Nov". */
export const shortDay = (isoDate: string) =>
  new Date(`${isoDate.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

/** ISO date-time → "10:42" today, otherwise "Mon 18 Nov". */
export function when(isoDateTime: string): string {
  const date = new Date(isoDateTime);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  }
  return shortDay(isoDateTime);
}

// ---- ASHA portal ----

const SMALL_WORDS = new Set(["a", "an", "and", "at", "for", "from", "in", "of", "on", "or", "the", "to", "with"]);

/** "no dose for 5 days" → "No Dose for 5 Days". Keeps words like TB and NAAT as they are. */
export function titleCase(text: string): string {
  return text
    .split(" ")
    .map((word, i) =>
      i > 0 && SMALL_WORDS.has(word.toLowerCase())
        ? word.toLowerCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

export const ACTION_TYPE: Record<string, string> = {
  call: "Phone Call",
  asha_visit: "Home Visit",
  isoscreen_test: "IsoScreen Test",
  side_effect_referral: "Side-Effect Review",
};

/** Treatment is 6 months: 2 months intensive phase (HRZE), then 4 months continuation (HRE). */
export function treatmentStage(days: number): { month: number; phase: string } {
  return {
    month: Math.min(6, Math.floor(days / 30) + 1),
    phase: days < 56 ? "Intensive Phase" : "Continuation Phase",
  };
}

/** Today as "YYYY-MM-DD" in the browser's time zone (matches the API's dates). */
export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Same bands as the server (app/inference/scoring.py): the threshold sits at 50%. */
export const bandOf = (risk: number | null): RiskBand | null =>
  risk === null ? null : risk >= 0.5 ? "high" : risk >= 0.35 ? "moderate" : "low";
