"""Shapes of the data the API sends and receives (the "API contract").

Pydantic checks every response against these classes, and the /docs page
shows them to the front end team. If you change a field here, update the
matching TypeScript type in apps/web/lib/api.ts.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Patient(BaseModel):
    """One synthetic patient on TB treatment. Same fields as the generator CSV."""

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


class RiskEntry(BaseModel):
    """A patient's dropout risk for this week, with the reasons behind it."""

    patient: Patient
    risk_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(description="Top reasons, most important first")
    is_mock: bool


ActionType = Literal["sms", "home_visit", "nutrition_support"]
ActionStatus = Literal["pending", "approved", "rejected"]


class Action(BaseModel):
    """A next step the AI agent suggests. A person must approve it before anything is sent."""

    action_id: int
    patient_id: str
    type: ActionType
    draft: str = Field(description="Message or note drafted for the health worker")
    status: ActionStatus = "pending"
