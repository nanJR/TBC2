"""/patients and /risk: the district dashboard's view of patients on treatment."""

from fastapi import APIRouter, HTTPException, Query

from app.mock_data import PATIENTS, mock_risk
from app.schemas import Patient, RiskEntry

router = APIRouter(tags=["patients"])


@router.get("/patients", response_model=list[Patient])
def list_patients() -> list[Patient]:
    return list(PATIENTS.values())


@router.get("/patients/{patient_id}", response_model=Patient)
def get_patient(patient_id: str) -> Patient:
    if patient_id not in PATIENTS:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PATIENTS[patient_id]


@router.get("/risk/weekly", response_model=list[RiskEntry])
def weekly_risk(limit: int = Query(default=20, ge=1, le=100)) -> list[RiskEntry]:
    """Patients most likely to stop treatment this week, highest risk first."""
    entries = [mock_risk(p) for p in PATIENTS.values()]
    entries.sort(key=lambda e: e.risk_score, reverse=True)
    return entries[:limit]
