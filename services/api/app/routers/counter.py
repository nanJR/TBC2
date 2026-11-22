"""The counter portal: ABHA lookup, recent screenings, and the practitioner's decision.

The practitioner sees the risk and the recommended action, then decides by hand:
forward the person to an ASHA, or dismiss with a reason. Each screening is decided once.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.mock_data import ABHA_DEMO, ASHAS, CASES, SCREENINGS, abha_key, case_from
from app.schemas import AbhaLookup, AbhaRecord, Case, DismissIn, ForwardIn, Screening

router = APIRouter(tags=["counter"])


@router.post("/abha/lookup", response_model=AbhaRecord)
def abha_lookup(body: AbhaLookup) -> AbhaRecord:
    """Fetch medical history for an ABHA number. Needs the person's consent.

    Simulated: four synthetic demo records, no connection to ABDM. The number is only
    hashed for the lookup and never stored.
    """
    if not body.consent:
        raise HTTPException(status_code=403, detail="The person's consent is needed first")
    record = ABHA_DEMO.get(abha_key(body.abha_number))
    if record is None:
        raise HTTPException(status_code=404, detail="No record found for this ABHA number")
    return record


@router.get("/screenings", response_model=list[Screening])
def list_screenings(limit: int = 20) -> list[Screening]:
    """Newest first."""
    newest = sorted(SCREENINGS.values(), key=lambda s: s.screened_at, reverse=True)
    return newest[: max(1, min(limit, 200))]


def _pending(screening_id: str) -> Screening:
    screening = SCREENINGS.get(screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="Screening not found")
    if screening.decision != "pending":
        raise HTTPException(status_code=409, detail="This screening is already decided")
    return screening


@router.post("/screenings/{screening_id}/forward", response_model=Case)
def forward(screening_id: str, body: ForwardIn) -> Case:
    """Send the person's details to an ASHA in their district, who has 48 h to reach them."""
    screening = _pending(screening_id)
    if not body.consent_contact:
        raise HTTPException(status_code=403, detail="The person must agree to be contacted")
    # Give the case to the ASHA with the fewest open cases in that district.
    open_cases = [c for c in CASES.values() if c.status not in ("on_treatment", "closed")]
    asha = min(
        ASHAS[screening.district],
        key=lambda name: sum(c.asha_name == name for c in open_cases),
    )
    case = case_from(screening, datetime.now(), asha)
    case.is_mock = screening.is_mock
    CASES[case.case_id] = case
    screening.decision, screening.case_id = "forwarded", case.case_id
    return case


@router.post("/screenings/{screening_id}/dismiss", response_model=Screening)
def dismiss(screening_id: str, body: DismissIn) -> Screening:
    screening = _pending(screening_id)
    screening.decision, screening.dismiss_reason = "dismissed", body.reason
    return screening
