"""Score one uploaded cough or X-ray. Shared by /screen (counter) and /cases (ASHA).

Uploads are read into memory, scored and thrown away. Nothing here writes a file.
"""

import io
from typing import Literal

import numpy as np
import soundfile
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app.inference.audio import describe, load_one_second, log_mel
from app.inference.image import MAX_COLOUR_DIFFERENCE, colour_difference, heatmap_png, preprocess
from app.inference.referral import rescale
from app.inference.registry import get_model

MAX_COUGH_BYTES = 5 * 1024 * 1024
MAX_XRAY_BYTES = 15 * 1024 * 1024

# Stop Pillow from unpacking a tiny file into a gigantic picture.
Image.MAX_IMAGE_PIXELS = 40_000_000

RiskBand = Literal["low", "moderate", "high"]


class ModelScore(BaseModel):
    """One model's score, with what it's allowed to be used for."""

    score: float = Field(ge=0, le=1, description="The model's raw score")
    flagged: bool = Field(description="True if the score reached the model's own threshold")
    counts_towards_referral: bool = Field(description="False means shown for information only")
    status: str
    note: str
    version: str


def risk_of(task: str, result: ModelScore | None) -> float | None:
    """The score shown to users: stretched so the model's own threshold sits at 50%."""
    model = get_model(task)
    if result is None or model is None:
        return None
    return round(rescale(result.score, model.threshold), 4)


def band_of(risk: float | None) -> RiskBand | None:
    """Low under 35%, moderate up to the threshold (50%), high from the threshold up."""
    if risk is None:
        return None
    if risk >= 0.5:
        return "high"
    return "moderate" if risk >= 0.35 else "low"


def read_limited(upload: UploadFile, limit: int) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{upload.filename} is too large")
    return data


def score_cough(upload: UploadFile) -> ModelScore | None:
    model = get_model("cough")
    if model is None:
        return None
    data = read_limited(upload, MAX_COUGH_BYTES)
    try:
        # Check it really is a sound file before doing anything else with it.
        soundfile.info(io.BytesIO(data))
        audio = load_one_second(io.BytesIO(data))
    except (soundfile.LibsndfileError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail="Could not read the cough file") from error
    if audio is None:
        raise HTTPException(
            status_code=422,
            detail="The recording is too short or too quiet. Record again in a quieter spot.",
        )
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


def score_xray(upload: UploadFile) -> tuple[ModelScore, str] | None:
    """Returns the score and a heatmap PNG (base64), or None if no X-ray model is installed."""
    model = get_model("xray")
    if model is None:
        return None
    data = read_limited(upload, MAX_XRAY_BYTES)
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
