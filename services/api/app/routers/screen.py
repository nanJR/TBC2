"""/screen: symptoms, a cough clip and an optional X-ray in; the next step out.

Uploads are held in memory only and thrown away after scoring. A live site could
receive real people's coughs, and this project must never keep real patient data.
"""

import io
from typing import Annotated, Literal

import numpy as np
import soundfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.formparsers import MultiPartParser

from app.inference.audio import describe, load_one_second, log_mel
from app.inference.image import MAX_COLOUR_DIFFERENCE, colour_difference, heatmap_png, preprocess
from app.inference.referral import NextStep, Symptom, Vulnerability, decide, rescale
from app.inference.registry import get_model

router = APIRouter(prefix="/screen", tags=["screening"])

MAX_COUGH_BYTES = 5 * 1024 * 1024
MAX_XRAY_BYTES = 15 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_COUGH_BYTES + MAX_XRAY_BYTES + 64 * 1024
MIN_AGE_FOR_MODELS = 15  # WHO recommends CAD for people aged 15 and over

# The web framework normally writes uploads over 1 MB to a temporary file. Raising this
# limit keeps every allowed upload in memory. main.py refuses larger requests up front.
MultiPartParser.spool_max_size = MAX_REQUEST_BYTES

# Stop Pillow from unpacking a tiny file into a gigantic picture.
Image.MAX_IMAGE_PIXELS = 40_000_000


class ModelScore(BaseModel):
    """One model's score, with what it's allowed to be used for."""

    score: float = Field(ge=0, le=1, description="The model's raw score")
    flagged: bool = Field(description="True if the score reached the model's own threshold")
    counts_towards_referral: bool = Field(description="False means shown for information only")
    status: str
    note: str
    version: str


class ScreenResult(BaseModel):
    """What the back end sends back after screening one person."""

    next_step: NextStep
    reasons: list[str]
    cough: ModelScore | None = None
    xray: ModelScore | None = None
    xray_heatmap_png: str | None = Field(default=None, description="Base64 PNG")
    risk_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Highest counted score, rescaled so each threshold is 0.5. Not a probability",
    )
    notes: list[str] = Field(description="Limits of this result, to show the user")
    is_mock: bool = Field(description="True only if a fake score was used")


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{upload.filename} is too large")
    return data


def _score_cough(upload: UploadFile) -> ModelScore | None:
    model = get_model("cough")
    if model is None:
        return None
    data = _read_limited(upload, MAX_COUGH_BYTES)
    try:
        # Check it really is a sound file before doing anything else with it.
        soundfile.info(io.BytesIO(data))
        audio = load_one_second(io.BytesIO(data))
    except (soundfile.LibsndfileError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail="Could not read the cough file") from error
    if audio is None:
        raise HTTPException(status_code=422, detail="The cough recording is too short or silent")
    if model.input_kind == "log_mel":
        inputs = log_mel(audio)[np.newaxis, np.newaxis]
    elif model.input_kind == "features168":
        inputs = describe(audio)[np.newaxis].astype(np.float32)
    else:
        # A model that also needs clinical answers can't run until /screen collects them.
        return None
    score = float(model.run(inputs)[0].ravel()[0])
    return ModelScore(
        score=round(score, 4),
        flagged=score >= model.threshold,
        counts_towards_referral=model.counts_towards_referral,
        status=model.status,
        note=model.note,
        version=model.version,
    )


def _score_xray(upload: UploadFile) -> tuple[ModelScore, str] | None:
    model = get_model("xray")
    if model is None:
        return None
    data = _read_limited(upload, MAX_XRAY_BYTES)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=422, detail="Could not read the X-ray image") from error
    if colour_difference(image) > MAX_COLOUR_DIFFERENCE:
        raise HTTPException(status_code=422, detail="This looks like a colour photo, not an X-ray")
    probabilities, cams = model.run(preprocess(image))
    score = float(probabilities.ravel()[0])
    result = ModelScore(
        score=round(score, 4),
        flagged=score >= model.threshold,
        counts_towards_referral=model.counts_towards_referral,
        status=model.status,
        note=model.note,
        version=model.version,
    )
    return result, heatmap_png(image, cams[0])


@router.post("", response_model=ScreenResult)
def screen(
    age: Annotated[int, Form(ge=0, le=120)],
    symptoms: Annotated[list[Symptom] | None, Form()] = None,
    vulnerabilities: Annotated[list[Vulnerability] | None, Form()] = None,
    image_source: Annotated[Literal["digital", "phone_photo"], Form()] = "digital",
    cough: Annotated[UploadFile | None, File(description="WAV sound file")] = None,
    xray: Annotated[UploadFile | None, File(description="Chest X-ray image")] = None,
) -> ScreenResult:
    """Screen one person. Symptoms always count, whatever the models say."""
    symptom_set, vulnerability_set = set(symptoms or []), set(vulnerabilities or [])
    if age > 60:
        vulnerability_set.add("over_60")
    notes = [
        "Prototype for learning only. Not for clinical use.",
        "A positive screen must be confirmed with a NAAT before starting treatment.",
    ]

    cough_score, xray_score, heatmap = None, None, None
    if age >= MIN_AGE_FOR_MODELS:
        if cough is not None:
            cough_score = _score_cough(cough)
        if xray is not None:
            scored = _score_xray(xray)
            if scored is not None:
                xray_score, heatmap = scored
                if image_source == "phone_photo":
                    notes.append("This model hasn't been tested on phone photos of X-ray film.")
    elif cough is not None or xray is not None:
        notes.append("The models are only used for people aged 15 and over.")

    xray_flagged = bool(xray_score and xray_score.flagged and xray_score.counts_towards_referral)
    next_step, reasons = decide(
        symptom_set, vulnerability_set, xray_flagged, xray_scored=xray_score is not None
    )

    if next_step != "naat":
        notes.append("This doesn't rule out TB. Many people with TB have no symptoms.")
    if cough_score and not cough_score.counts_towards_referral:
        notes.append("The cough score is experimental and did not affect this result.")

    counted = []
    for task, result in (("cough", cough_score), ("xray", xray_score)):
        model = get_model(task)
        if result and model and result.counts_towards_referral:
            counted.append(rescale(result.score, model.threshold))

    return ScreenResult(
        next_step=next_step,
        reasons=reasons,
        cough=cough_score,
        xray=xray_score,
        xray_heatmap_png=heatmap,
        risk_score=round(max(counted), 4) if counted else None,
        notes=notes,
        is_mock=False,
    )
