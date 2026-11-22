"""/patients and /risk: patients on treatment, their daily doses and IsoScreen tests."""

from fastapi import APIRouter, HTTPException, Query

from app.mock_data import DISTRICTS, PATIENTS, TODAY, mock_risk, record_dose
from app.schemas import DoseIn, IsoScreenIn, IsoScreenTest, Patient, RiskEntry

router = APIRouter(tags=["patients"])


@router.get("/districts", response_model=list[str])
def list_districts() -> list[str]:
    """The districts this prototype covers, for drop-down lists."""
    return sorted(DISTRICTS)


@router.get("/patients", response_model=list[Patient])
def list_patients() -> list[Patient]:
    return list(PATIENTS.values())


def _patient(patient_id: str) -> Patient:
    if patient_id not in PATIENTS:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PATIENTS[patient_id]


@router.get("/patients/{patient_id}", response_model=Patient)
def get_patient(patient_id: str) -> Patient:
    return _patient(patient_id)


@router.post("/patients/{patient_id}/doses", response_model=RiskEntry)
def log_dose(patient_id: str, body: DoseIn) -> RiskEntry:
    """Record today's dose (taken or missed). Once a day; returns the updated risk."""
    patient = _patient(patient_id)
    if patient.last_dose_logged_on == TODAY:
        raise HTTPException(status_code=409, detail="Today's dose is already recorded")
    record_dose(patient, body.status)
    return mock_risk(patient)


@router.post("/patients/{patient_id}/isoscreen", response_model=RiskEntry)
def log_isoscreen(patient_id: str, body: IsoScreenIn) -> RiskEntry:
    """Record an IsoScreen urine test. Only for regimens that contain isoniazid."""
    patient = _patient(patient_id)
    if patient.regimen != "drug-sensitive":
        raise HTTPException(
            status_code=422, detail="IsoScreen checks isoniazid, which isn't in this regimen"
        )
    patient.isoscreen_tests.append(
        IsoScreenTest(
            day_on_treatment=patient.days_on_treatment,
            result=body.result,
            hours_since_dose=body.hours_since_dose,
        )
    )
    return mock_risk(patient)


@router.get("/risk/weekly", response_model=list[RiskEntry])
def weekly_risk(
    limit: int = Query(default=20, ge=1, le=500), district: str | None = None
) -> list[RiskEntry]:
    """Patients most likely to stop treatment this week, highest risk first."""
    entries = [mock_risk(p) for p in PATIENTS.values() if district in (None, p.district)]
    entries.sort(key=lambda e: e.risk_score, reverse=True)
    return entries[:limit]
