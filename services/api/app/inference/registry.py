"""Find and load the exported models.

Each model lives in its own folder, as two files:
    <MODEL_DIR>/xray/model.onnx    and  model.json
    <MODEL_DIR>/cough/model.onnx   and  model.json

To replace a model, replace those two files and restart the server. No code changes.
Git ignores the folder (weights never go in git). If a model's files are missing, its
score is simply left out of the response.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort

from app.config import settings

Task = Literal["xray", "cough"]


@dataclass(frozen=True)
class LoadedModel:
    """A model ready to run, plus the facts about it from model.json."""

    version: str
    threshold: float
    counts_towards_referral: bool
    status: str  # e.g. "experimental"
    note: str  # shown to the user with the score
    session: ort.InferenceSession
    # How a cough model wants its sound: features168, log_mel or log_mel_clinical.
    input_kind: str = "features168"

    def run(self, inputs: np.ndarray) -> list[np.ndarray]:
        name = self.session.get_inputs()[0].name
        return self.session.run(None, {name: inputs})


@lru_cache
def get_model(task: Task) -> LoadedModel | None:
    """Load a model once and keep it. Returns None if its files aren't there."""
    folder = Path(settings.model_dir) / task
    if not (folder / "model.onnx").exists() or not (folder / "model.json").exists():
        return None
    meta = json.loads((folder / "model.json").read_text())
    return LoadedModel(
        version=meta["version"],
        threshold=float(meta["threshold"]),
        counts_towards_referral=bool(meta["counts_towards_referral"]),
        status=meta["status"],
        note=meta["note"],
        input_kind=meta.get("input_kind", "features168"),
        session=ort.InferenceSession(folder / "model.onnx", providers=["CPUExecutionProvider"]),
    )
