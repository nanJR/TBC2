"""Shapes of the data the API sends and receives (the "API contract").

Pydantic checks every response against these classes, and the /docs page
shows them to the front end team. If you change a field here, update the
matching TypeScript type in apps/web/lib/api.ts.

The journey these shapes follow:
counter Screening → (forwarded by the practitioner) → ASHA Case → (NAAT confirms TB,
the Medical Officer starts treatment) → Patient, tracked every day.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.inference.referral import NextStep, Symptom, Vulnerability
from app.inference.scoring import RiskBand

DoseDay = Literal["taken", "missed"]

# ---------------------------------------------------------------- treatment tracking

# IsoScreen is a urine strip that turns colour if isoniazid (one of the TB medicines)
# was taken in the last 1-2 days. It is a spot check on the patient's own dose reports.
IsoScreenResult = Literal["inh_detected", "inh_not_detected", "indeterminate"]


class IsoScreenTest(BaseModel):
    """One unannounced IsoScreen urine test.

    "inh_not_detected" on a day the patient reported a dose means the self-reports
    are less trustworthy. Only regimens that contain isoniazid can be checked this way.
    """

    day_on_treatment: int
    result: IsoScreenResult
    hours_since_dose: int | None = Field(
        default=None, description="Most readable 6 to 48 hours after a dose"
    )


# Adult weight bands used for daily fixed-dose combination tablets (NTEP).
WeightBand = Literal["25-34", "35-49", "50-64", "65-75", "over-75"]


class Patient(BaseModel):
    """One synthetic patient on TB treatment.

    The first fields match the generator CSV. The care-tracking fields at the
    end (dose log, IsoScreen tests, side effects) are mock data for now.
    """

    patient_id: str
    age: int
    sex: Literal["M", "F"]
    district: str
    lat: float
    lon: float
    distance_to_clinic_km: float
    regimen: Literal["drug-sensitive", "drug-resistant"]
    days_on_treatment: int
    doses_missed_last_4_weeks: int
    alcohol_use: bool
    undernourished: bool
    previously_treated: bool
    has_phone: bool
    gets_nutrition_support: bool
    dose_log_last_28_days: list[DoseDay] = Field(
        description="Daily self-reports (99DOTS style), oldest first, last recorded day last"
    )
    last_dose_logged_on: date | None = Field(
        default=None, description="The day of the newest entry in the dose log"
    )
    missed_in_a_row: int = Field(description="Days in a row with no dose, up to the last log")
    isoscreen_tests: list[IsoScreenTest] = Field(description="Urine tests so far, oldest first")
    side_effect_reported: bool
    asha_name: str | None = None
    phc: str | None = None
    weight_band: WeightBand | None = None
    case_id: str | None = Field(default=None, description="Set if they came through a counter")


# The missed-dose ladder: a call after 3 missed days in a row, an ASHA visit after 7.
LadderStep = Literal["on_track", "call", "asha_visit"]


class RiskEntry(BaseModel):
    """A patient's dropout risk for this week, with the reasons behind it."""

    patient: Patient
    risk_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(description="Top reasons, most important first")
    ladder_step: LadderStep
    isoscreen_every_days: int | None = Field(
        description="14 for high-risk patients, 30 for others, None if there is no isoniazid"
    )
    is_mock: bool


class DoseIn(BaseModel):
    status: DoseDay


class IsoScreenIn(BaseModel):
    result: IsoScreenResult
    hours_since_dose: int | None = Field(default=None, ge=0, le=240)


# ---------------------------------------------------------------- suggested actions

ActionType = Literal["call", "asha_visit", "isoscreen_test", "side_effect_referral"]
ActionStatus = Literal["pending", "approved", "rejected"]


class Action(BaseModel):
    """A next step TBC² suggests. A person must approve it before anything is sent."""

    action_id: int
    patient_id: str
    type: ActionType
    reason: str = Field(description="Why TBC² suggests this, in plain words")
    draft: str = Field(description="Message or note drafted for the health worker")
    status: ActionStatus = "pending"


# ---------------------------------------------------------------- counter (pharmacy)


class AbhaLookup(BaseModel):
    """The ABHA number (14 digits, shown as 12-3456-7890-1234) and the person's consent."""

    abha_number: str = Field(pattern=r"^\d{2}-\d{4}-\d{4}-\d{4}$")
    consent: bool = Field(description="The person agreed to share their records for TB screening")


class AbhaRecord(BaseModel):
    """Medical history fetched with consent. Simulated: no real ABDM connection."""

    abha_last4: str
    age: int
    sex: Literal["M", "F"]
    district: str
    history: list[Vulnerability] = Field(description="Ticks the history checklist")
    conditions: list[str] = Field(description="Readable notes from the record")
    is_mock: bool


ScreeningDecision = Literal["pending", "forwarded", "dismissed"]
DismissReason = Literal[
    "declined", "already_on_treatment", "referred_elsewhere", "low_risk", "other"
]


class Screening(BaseModel):
    """One person checked at the counter. Answers and scores only, never the recording."""

    screening_id: str
    screened_at: datetime
    practitioner: str
    age: int
    sex: Literal["M", "F"]
    district: str
    has_phone: bool
    symptoms: list[Symptom]
    history: list[Vulnerability]
    abha_linked: bool
    cough_risk: float | None = Field(description="0-1, the threshold sits at 0.5")
    risk_band: RiskBand | None
    recommended_action: NextStep
    reasons: list[str]
    decision: ScreeningDecision = "pending"
    dismiss_reason: DismissReason | None = None
    case_id: str | None = None
    is_mock: bool


class ForwardIn(BaseModel):
    consent_contact: bool = Field(description="The person agreed to be contacted by an ASHA")


class DismissIn(BaseModel):
    reason: DismissReason


# ---------------------------------------------------------------- ASHA cases

CaseStatus = Literal[
    "new",  # forwarded, ASHA has not reached the person yet
    "contacted",
    "xray_booked",
    "xray_done",
    "risk_combined",
    "naat_positive",  # TB confirmed, waiting for the Medical Officer to start treatment
    "on_treatment",
    "closed",
]
NaatResult = Literal[
    "mtb_detected_rr_not_detected",
    "mtb_detected_rr_detected",
    "mtb_not_detected",
    "inconclusive",
]


class VanSlot(BaseModel):
    """One day the mobile X-ray van visits a site."""

    slot_id: str
    district: str
    site: str
    day: date
    capacity: int
    booked: int


class Case(BaseModel):
    """A person forwarded from the counter to an ASHA, from first contact to treatment."""

    case_id: str
    screening_id: str
    forwarded_at: datetime
    practitioner: str
    age: int
    sex: Literal["M", "F"]
    district: str
    has_phone: bool
    symptoms: list[Symptom]
    history: list[Vulnerability]
    abha_linked: bool
    cough_risk: float | None
    counter_action: NextStep
    counter_reasons: list[str]
    asha_name: str
    status: CaseStatus = "new"
    contact_due_at: datetime = Field(description="ASHA should reach the person within 48 h")
    contact_attempts: int = 0
    contacted_at: datetime | None = None
    sputum_collected_at: datetime | None = None
    xray_slot: VanSlot | None = None
    xray_source: Literal["upload", "van_reading"] | None = None
    xray_risk: float | None = Field(default=None, description="0-1, the threshold sits at 0.5")
    van_reading: Literal["normal", "abnormal"] | None = None
    combined_risk: float | None = None
    combined_band: RiskBand | None = None
    combined_action: NextStep | None = None
    combined_reasons: list[str] = []
    naat_result: NaatResult | None = None
    naat_attempts: int = 0
    mo_name: str | None = Field(default=None, description="Medical Officer who started treatment")
    nikshay_id: str | None = Field(default=None, description="Typed in by hand; no connection")
    notified_in_nikshay: bool = False
    patient_id: str | None = None
    closed_reason: str | None = None
    is_mock: bool


class ContactIn(BaseModel):
    reached: bool


class ScheduleIn(BaseModel):
    slot_id: str


class VanReadingIn(BaseModel):
    reading: Literal["normal", "abnormal"]


class NaatIn(BaseModel):
    result: NaatResult


class StartTreatmentIn(BaseModel):
    """Recorded by the ASHA after the Medical Officer at the PHC starts treatment."""

    mo_name: str = Field(min_length=2, max_length=80)
    phc: str = Field(min_length=2, max_length=80)
    weight_band: WeightBand
    nikshay_id: str | None = Field(default=None, max_length=20)
    notified_in_nikshay: bool = False


class CloseIn(BaseModel):
    reason: Literal["xray_clear", "not_reached", "moved_away", "declined", "other"]


class Overview(BaseModel):
    """Counts for the patient-journey card, from the first check to treatment."""

    screened: int
    forwarded: int
    tested: int
    on_treatment: int
    awaiting_contact: int
    overdue: int
    is_mock: bool
