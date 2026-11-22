"""Things both portals need: the district list, the patient-journey counts, and who
is signed in. Any signed-in role may call these."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import User, require
from app.mock_data import CASES, DISTRICTS, SCREENINGS
from app.schemas import Overview

router = APIRouter(tags=["shared"])


class Me(BaseModel):
    signed_in: bool
    email: str | None = None
    role: str | None = None
    full_name: str | None = None
    district: str | None = None
    place: str | None = None


@router.get("/me", response_model=Me)
def me(user: Annotated[User | None, Depends(require("practitioner", "asha"))]) -> Me:
    """The signed-in user's role and place. signed_in is false when login is turned off."""
    if user is None:
        return Me(signed_in=False)
    return Me(
        signed_in=True,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        district=user.district,
        place=user.place,
    )


@router.get("/districts", response_model=list[str])
def list_districts() -> list[str]:
    """The districts this prototype covers, for drop-down lists."""
    return sorted(DISTRICTS)


@router.get("/overview", response_model=Overview)
def overview(district: str | None = None) -> Overview:
    """Counts for the patient-journey card, from the counter check to treatment."""
    screenings = [s for s in SCREENINGS.values() if district in (None, s.district)]
    cases = [c for c in CASES.values() if district in (None, c.district)]
    now = datetime.now()
    return Overview(
        screened=len(screenings),
        forwarded=sum(s.decision == "forwarded" for s in screenings),
        tested=sum(
            c.xray_source is not None or c.naat_result not in (None, "inconclusive") for c in cases
        ),
        on_treatment=sum(c.status == "on_treatment" for c in cases),
        awaiting_contact=sum(c.status == "new" for c in cases),
        overdue=sum(c.status == "new" and now > c.contact_due_at for c in cases),
        is_mock=True,
    )
