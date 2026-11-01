"""Pack the interim cough model into an ONNX file the server can run.

Needs the checkpoint from cough/train_classifier.py. Run from the ml/ folder:
    uv run python export/export_cough.py

This is the small logistic regression trained on the Kaggle data. It's served only as an
experiment: on clinic-only test people its specificity is 25%, so counting it would send
almost everyone for a test. `counts_towards_referral` stays false until a better model
passes the checks in docs/cough-training-runbook.md.

Output (git ignores it): services/api/models/cough/model.onnx and model.json
"""

import json
import sys
from pathlib import Path

import joblib
import librosa
import numpy as np
import onnxruntime as ort
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.inference.audio import describe, load_one_second

CHECKPOINT = ROOT / "ml" / "checkpoints" / "cough_logreg.joblib"
FEATURES = ROOT / "data" / "processed" / "cough_features.npz"
AUDIO = ROOT / "data" / "raw" / "Cough_Audio" / "audio_wav"
RESULTS = ROOT / "ml" / "cough" / "results" / "logreg.json"
OUT_DIR = ROOT / "services" / "api" / "models" / "cough"
CHECK_CLIPS = 50
MAX_SCORE_DIFFERENCE = 0.001


class CoughModel(torch.nn.Module):
    """The scaler and logistic regression written as one small network."""

    def __init__(self, mean, scale, coef, intercept):
        super().__init__()
        self.register_buffer("mean", torch.tensor(mean, dtype=torch.float32))
        self.register_buffer("scale", torch.tensor(scale, dtype=torch.float32))
        self.register_buffer("coef", torch.tensor(coef, dtype=torch.float32))
        self.register_buffer("intercept", torch.tensor(intercept, dtype=torch.float32))

    def forward(self, features):
        z = (features - self.mean) / self.scale
        return torch.sigmoid((z * self.coef).sum(dim=1) + self.intercept)


def main() -> None:
    bundle = joblib.load(CHECKPOINT)
    scaler, classifier = bundle["pipeline"].steps[0][1], bundle["pipeline"].steps[-1][1]
    model = CoughModel(
        scaler.mean_, scaler.scale_, classifier.coef_[0], classifier.intercept_[0]
    ).eval()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUT_DIR / "model.onnx"
    torch.onnx.export(
        model,
        (torch.zeros(1, 168),),
        onnx_path,
        input_names=["features"],
        output_names=["probability"],
        dynamic_axes={"features": {0: "batch"}, "probability": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )

    # ---- Parity check: raw sound file -> server code -> ONNX, against the original ----
    data = np.load(FEATURES)
    expected = bundle["pipeline"].predict_proba(data["features"])[:, 1]
    picks = np.random.default_rng(0).choice(len(expected), CHECK_CLIPS, replace=False)
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    differences = []
    for i in picks:
        audio = load_one_second(AUDIO / str(data["paths"][i]))
        features = describe(audio)[np.newaxis].astype(np.float32)
        score = session.run(None, {"features": features})[0].ravel()[0]
        differences.append(abs(float(score) - float(expected[i])))
    worst = max(differences)
    print(f"Parity on {CHECK_CLIPS} clips (librosa {librosa.__version__}): worst {worst:.6f}")
    if worst > MAX_SCORE_DIFFERENCE:
        onnx_path.unlink()
        raise SystemExit(f"Exported model disagrees with the original by {worst:.4f}")

    results = json.loads(RESULTS.read_text())
    meta = {
        "version": "logreg-kaggle-interim-v1",
        "task": "cough",
        "threshold": float(bundle["threshold"]),
        "counts_towards_referral": False,
        "status": "experimental",
        "note": (
            "Experimental model from a small dataset. It is shown for information only and "
            "can't support a referral on its own."
        ),
        "training_data": "Kaggle TB cough set (TBscreen and Coswara)",
        "population": "Not established. Training data mixes clinic and home recordings.",
        "test_results": {
            "tbscreen_only": results["test_tbscreen_only"],
            "tbscreen_only_5fold_cv": results["tbscreen_only_5fold_cv"],
        },
    }
    (OUT_DIR / "model.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Saved {OUT_DIR}")


if __name__ == "__main__":
    main()
