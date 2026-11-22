"""The ASHA portal: forwarded cases, from first contact to the start of treatment.

Steps, in order (each endpoint checks the case is at the right step, else 409):
1. contact: try to reach the person (48 h deadline). Not reached → try again.
2. sputum: for presumptive TB, collect sputum at first contact for the NAAT. Don't
   wait for the X-ray van.
3. schedule: book the weekly mobile X-ray van.
4. xray (upload, scored here) or van-reading (the van's own reading).
5. combine: one combined risk from the cough and X-ray, plus the next step.
6. naat: record the result. Inconclusive means a new sample and a repeat test.
7. start-treatment: the Medical Officer started treatment; the person joins tracking.
The X-ray image is scored in memory and never stored.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import db
from app.inference.referral import decide
from app.inference.scoring import band_of, risk_of, score_xray
from app.mock_data import CASES, VAN_SLOTS, start_treatment
from app.schemas import (
    Case,
    CloseIn,
    ContactIn,
    NaatIn,
    ScheduleIn,
    StartTreatmentIn,
    VanReadingIn,
    VanSlot,
)

router = APIRouter(tags=["cases"])

FINISHED = ("on_treatment", "closed")


@router.get("/van-slots", response_model=list[VanSlot])
def van_slots(district: str | None = None) -> list[VanSlot]:
    """Upcoming mobile X-ray van visits, soonest first."""
    slots = [s for s in VAN_SLOTS.values() if district is None or s.district == district]
    return sorted(slots, key=lambda s: (s.day, s.site))


@router.get("/cases", response_model=list[Case])
def list_cases(district: str | None = None) -> list[Case]:
    """Newest first."""
    cases = [c for c in CASES.values() if district in (None, c.district)]
    return sorted(cases, key=lambda c: c.forwarded_at, reverse=True)


def _case(case_id: str, *allowed: str) -> Case:
    """Find a case and check it is at one of the allowed steps."""
    case = CASES.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if allowed and case.status not in allowed:
        raise HTTPException(status_code=409, detail=f"Not possible while the case is {case.status}")
    db.save_case(case)
    return case


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    return _case(case_id)


@router.post("/cases/{case_id}/contact", response_model=Case)
def contact(case_id: str, body: ContactIn) -> Case:
    case = _case(case_id, "new")
    case.contact_attempts += 1
    if body.reached:
        case.status, case.contacted_at = "contacted", datetime.now()
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/sputum", response_model=Case)
def sputum(case_id: str) -> Case:
    """Sputum collected and sent to the TB Unit for a NAAT (Truenat or CBNAAT)."""
    case = _case(case_id, "contacted", "xray_booked", "xray_done", "risk_combined")
    if case.sputum_collected_at is not None:
        raise HTTPException(status_code=409, detail="A sample is already with the lab")
    case.sputum_collected_at = datetime.now()
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/schedule", response_model=Case)
def schedule(case_id: str, body: ScheduleIn) -> Case:
    case = _case(case_id, "contacted", "xray_booked")
    slot = VAN_SLOTS.get(body.slot_id)
    if slot is None or slot.district != case.district:
        raise HTTPException(status_code=404, detail="No van visit with that ID in this district")
    if slot.booked >= slot.capacity:
        raise HTTPException(status_code=409, detail="That van visit is full")
    if case.xray_slot is not None:  # moving to another day frees the old place
        old = VAN_SLOTS[case.xray_slot.slot_id]
        old.booked -= 1
        db.save_slot(old)
    slot.booked += 1
    db.save_slot(slot)
    case.xray_slot, case.status = slot.model_copy(), "xray_booked"
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/xray", response_model=Case)
def upload_xray(
    case_id: str, xray: Annotated[UploadFile, File(description="Chest X-ray image")]
) -> Case:
    """Score the X-ray from the van. Can be redone until the combined risk is worked out."""
    case = _case(case_id, "xray_booked", "xray_done")
    scored = score_xray(xray)
    if scored is None:
        raise HTTPException(status_code=503, detail="X-ray scoring isn't available right now")
    xray_score, _heatmap = scored
    case.xray_source, case.van_reading = "upload", None
    case.xray_risk, case.status = risk_of("xray", xray_score), "xray_done"
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/van-reading", response_model=Case)
def van_reading(case_id: str, body: VanReadingIn) -> Case:
    """Use the van's own reading when the image itself isn't available."""
    case = _case(case_id, "xray_booked", "xray_done")
    case.xray_source, case.van_reading, case.xray_risk = "van_reading", body.reading, None
    case.status = "xray_done"
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/combine", response_model=Case)
def combine(case_id: str) -> Case:
    """One combined risk from the counter's cough score and the X-ray.

    The number is the higher of the two scores (each rescaled so its threshold is 0.5):
    a simple rule, not a trained model. The next step still follows the programme
    rules: symptoms always mean a NAAT, and a high X-ray risk adds one.
    """
    case = _case(case_id, "xray_done")
    xray_flagged = (case.xray_risk or 0) >= 0.5 or case.van_reading == "abnormal"
    scores = [r for r in (case.cough_risk, case.xray_risk) if r is not None]
    case.combined_risk = max(scores) if scores else None
    case.combined_band = band_of(case.combined_risk)
    case.combined_action, case.combined_reasons = decide(
        set(case.symptoms),
        set(case.history),
        xray_flagged,
        xray_scored=True,
        cough_flagged=(case.cough_risk or 0) >= 0.5,
    )
    case.status = "risk_combined"
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/naat", response_model=Case)
def naat(case_id: str, body: NaatIn) -> Case:
    """Record the NAAT result. Needs a sputum sample first."""
    case = _case(case_id, "contacted", "xray_booked", "xray_done", "risk_combined")
    if case.sputum_collected_at is None:
        raise HTTPException(status_code=409, detail="Collect a sputum sample first")
    case.naat_attempts += 1
    case.naat_result = body.result
    if body.result == "inconclusive":
        case.sputum_collected_at = None  # a fresh sample is needed for the repeat test
    elif body.result == "mtb_not_detected":
        case.status, case.closed_reason = "closed", "NAAT: MTB not detected"
    else:
        case.status = "naat_positive"
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/start-treatment", response_model=Case)
def begin_treatment(case_id: str, body: StartTreatmentIn) -> Case:
    """The PHC Medical Officer started treatment. The person joins daily tracking."""
    case = _case(case_id, "naat_positive")
    patient = start_treatment(case, body, case.naat_result)
    db.save_patient(patient)
    case.status, case.patient_id = "on_treatment", patient.patient_id
    case.mo_name, case.nikshay_id = body.mo_name, body.nikshay_id
    case.notified_in_nikshay = body.notified_in_nikshay
    db.save_case(case)
    return case


@router.post("/cases/{case_id}/close", response_model=Case)
def close(case_id: str, body: CloseIn) -> Case:
    case = _case(case_id)
    if case.status in FINISHED:
        raise HTTPException(status_code=409, detail="This case is already finished")
    case.status, case.closed_reason = "closed", body.reason.replace("_", " ")
    db.save_case(case)
    return case
