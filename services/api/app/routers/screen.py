"""/screen: turn a cough clip and an optional X-ray into one TB risk score.

For now this returns a FAKE ("mock") score so the front end can be built
before the real models exist. In Weeks 5-7 the fake numbers get replaced
by calls into app/inference/.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/screen", tags=["screening"])


class ScreenResult(BaseModel):
    """What the back end sends back after screening one person."""

    cough_score: float = Field(ge=0, le=1, description="0 = no sign of TB, 1 = strong sign")
    xray_score: float | None = Field(
        default=None, ge=0, le=1, description="Empty if no X-ray was uploaded"
    )
    risk_score: float = Field(ge=0, le=1, description="Combined TB risk")
    is_mock: bool = Field(description="True while we are still using fake scores")


@router.post("/mock", response_model=ScreenResult)
def screen_mock() -> ScreenResult:
    """Return a fixed fake result. Replace with real model calls later."""
    cough, xray = 0.62, 0.48
    return ScreenResult(
        cough_score=cough,
        xray_score=xray,
        # Simple average for now; we may weight the two models differently later.
        risk_score=round((cough + xray) / 2, 2),
        is_mock=True,
    )
