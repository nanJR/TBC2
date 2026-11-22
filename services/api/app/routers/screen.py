"""/screen: the counter check. Symptoms, history and a cough in; risk and next step out.

Uploads are held in memory only and thrown away after scoring. A live site could
receive real people's coughs, and this project must never keep real patient data.
Each call saves a Screening summary (answers and scores, never the files), so the
practitioner can forward it to an ASHA or dismiss it (see counter.py).
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.formparsers import MultiPartParser

from app import db
from app.inference.referral import NextStep, Symptom, Vulnerability, decide
from app.inference.scoring import (
    MAX_COUGH_BYTES,
    MAX_XRAY_BYTES,
    ModelScore,
    RiskBand,
    band_of,
    risk_of,
    score_cough,
    score_xray,
)
from app.mock_data import (
    DEMO_PRACTITIONER,
    DISTRICTS,
    MAX_SCREENINGS,
    SCREENINGS,
    next_screening_id,
)
from app.schemas import Screening

router = APIRouter(prefix="/screen", tags=["screening"])

MAX_REQUEST_BYTES = MAX_COUGH_BYTES + MAX_XRAY_BYTES + 64 * 1024
MIN_AGE_FOR_MODELS = 15  # WHO recommends CAD for people aged 15 and over

# The web framework normally writes uploads over 1 MB to a temporary file. Raising this
# limit keeps every allowed upload in memory. main.py refuses larger requests up front.
MultiPartParser.spool_max_size = MAX_REQUEST_BYTES


class ScreenResult(BaseModel):
    """What the back end sends back after screening one person."""

    screening_id: str
    next_step: NextStep
    reasons: list[str]
    cough: ModelScore | None = None
    xray: ModelScore | None = None
    xray_heatmap_png: str | None = Field(default=None, description="Base64 PNG")
    risk_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "The higher of the cough and X-ray scores, each rescaled so its threshold is 0.5. "
            "A simple rule, not a trained fusion model. Not a probability"
        ),
    )
    risk_band: RiskBand | None = None
    notes: list[str] = Field(description="Limits of this result, for the docs and API users")
    is_mock: bool = Field(description="True only if a fake score was used")


@router.post("", response_model=ScreenResult)
def screen(
    age: Annotated[int, Form(ge=0, le=120)],
    sex: Annotated[Literal["M", "F"], Form()],
    district: Annotated[str, Form()],
    symptoms: Annotated[list[Symptom] | None, Form()] = None,
    vulnerabilities: Annotated[list[Vulnerability] | None, Form()] = None,
    has_phone: Annotated[bool, Form()] = True,
    abha_linked: Annotated[bool, Form()] = False,
    image_source: Annotated[Literal["digital", "phone_photo"], Form()] = "digital",
    cough: Annotated[UploadFile | None, File(description="WAV sound file")] = None,
    xray: Annotated[UploadFile | None, File(description="Chest X-ray image")] = None,
) -> ScreenResult:
    """Screen one person. Symptoms always count, whatever the scores say."""
    if district not in DISTRICTS:
        raise HTTPException(status_code=422, detail="Unknown district")
    if len(SCREENINGS) >= MAX_SCREENINGS:
        raise HTTPException(status_code=507, detail="Screening list is full. Restart the server")
    symptom_set, history = set(symptoms or []), set(vulnerabilities or [])
    if age > 60:
        history.add("over_60")
    notes = ["A positive screen must be confirmed with a NAAT before starting treatment."]

    cough_score, xray_score, heatmap = None, None, None
    if age >= MIN_AGE_FOR_MODELS:
        if cough is not None:
            cough_score = score_cough(cough)
        if xray is not None:
            scored = score_xray(xray)
            if scored is not None:
                xray_score, heatmap = scored
                if image_source == "phone_photo":
                    notes.append("This model hasn't been tested on phone photos of X-ray film.")
    elif cough is not None or xray is not None:
        notes.append("The models are only used for people aged 15 and over.")

    xray_flagged = bool(xray_score and xray_score.flagged and xray_score.counts_towards_referral)
    # An experimental cough model may only suggest an X-ray (see referral.py).
    cough_flagged = bool(cough_score and cough_score.flagged)
    next_step, reasons = decide(
        symptom_set,
        history,
        xray_flagged,
        xray_scored=xray_score is not None,
        cough_flagged=cough_flagged,
    )

    if next_step != "naat":
        notes.append("This doesn't rule out TB. Many people with TB have no symptoms.")
    if cough_score and not cough_score.counts_towards_referral:
        notes.append("The cough score is experimental. It can suggest an X-ray, never a NAAT.")

    # Rescale each score so every model's threshold sits at 0.5, then take the higher.
    cough_risk, xray_risk = risk_of("cough", cough_score), risk_of("xray", xray_score)
    scores = [r for r in (cough_risk, xray_risk) if r is not None]
    risk_score = max(scores) if scores else None
    if len(scores) == 2:
        notes.append("The combined score is a simple rule, not a trained fusion model.")

    screening = Screening(
        screening_id=next_screening_id(),
        screened_at=datetime.now(),
        practitioner=DEMO_PRACTITIONER,
        age=age,
        sex=sex,
        district=district,
        has_phone=has_phone,
        symptoms=sorted(symptom_set),
        history=sorted(history),
        abha_linked=abha_linked,
        cough_risk=cough_risk,
        risk_band=band_of(cough_risk),
        recommended_action=next_step,
        reasons=reasons,
        is_mock=False,
    )
    SCREENINGS[screening.screening_id] = screening
    db.save_screening(screening)

    return ScreenResult(
        screening_id=screening.screening_id,
        next_step=next_step,
        reasons=reasons,
        cough=cough_score,
        xray=xray_score,
        xray_heatmap_png=heatmap,
        risk_score=risk_score,
        risk_band=band_of(risk_score),
        notes=notes,
        is_mock=False,
    )
