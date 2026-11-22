"""Shapes of the data the API sends and receives (the "API contract").

Pydantic checks every response against these classes, and the /docs page
shows them to the front end team. If you change a field here, update the
matching TypeScript type in apps/web/lib/api.ts.
"""

from typing import Literal

from pydantic import BaseModel, Field

DoseDay = Literal["taken", "missed"]


class GoldenCheck(BaseModel):
    """A surprise urine test that checks the patient's own dose reports.

    "mismatch" means the patient reported taking the medicine but the urine
    test found none. That makes the self-reports less trustworthy.
    """

    day_on_treatment: int
    result: Literal["match", "mismatch"]


class Patient(BaseModel):
    """One synthetic patient on TB treatment.

    The first fields match the generator CSV. The care-tracking fields at the
    end (dose log, golden checks, side effects) are mock data for now.
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
        description="Daily self-reports (99DOTS style), oldest first, today last"
    )
    missed_in_a_row: int = Field(description="Days in a row with no dose, up to today")
    golden_checks: list[GoldenCheck] = Field(description="Urine checks so far, oldest first")
    side_effect_reported: bool


# The missed-dose ladder: a call after 3 missed days in a row, an ASHA visit after 7.
LadderStep = Literal["on_track", "call", "asha_visit"]


class RiskEntry(BaseModel):
    """A patient's dropout risk for this week, with the reasons behind it."""

    patient: Patient
    risk_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(description="Top reasons, most important first")
    ladder_step: LadderStep
    golden_check_every_days: int = Field(
        description="14 for high-risk patients, 30 for everyone else"
    )
    is_mock: bool


ActionType = Literal["call", "asha_visit", "golden_check", "side_effect_referral"]
ActionStatus = Literal["pending", "approved", "rejected"]


class Action(BaseModel):
    """A next step the AI agent suggests. A person must approve it before anything is sent."""

    action_id: int
    patient_id: str
    type: ActionType
    reason: str = Field(description="Why the agent suggests this, in plain words")
    draft: str = Field(description="Message or note drafted for the health worker")
    status: ActionStatus = "pending"
