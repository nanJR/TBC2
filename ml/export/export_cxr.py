"""Pack the chest X-ray model into one ONNX file the server can run without PyTorch.

Needs the checkpoint from cxr/train_classifier.py and the features from
cxr/extract_features.py. Run from the ml/ folder:
    uv run python export/export_cxr.py

What goes in the file: the EfficientNet-B0 network, then the scaler and logistic
regression, joined into a single model. It gives two outputs:
- probability: the score for each image
- cam: a 7 x 7 heatmap of where the model looked

The heatmap needs no gradients. The classifier is a plain weighted sum of the averaged
network maps, so applying the same weights to each map, before averaging, shows how much
each part of the image added to the score.

Before saving, this checks the exported model against the original on real test images,
using the server's own image code. It stops with an error if they disagree.

Output (git ignores it): services/api/models/xray/model.onnx and model.json
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import onnxruntime as ort
import timm
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.inference.image import colour_difference, preprocess

MODEL_NAME = "efficientnet_b0"
CHECKPOINT = ROOT / "ml" / "checkpoints" / f"cxr_{MODEL_NAME}.joblib"
FEATURES = ROOT / "data" / "processed" / "cxr_features" / MODEL_NAME / "test.npz"
IMAGES = ROOT / "data" / "raw" / "CXR"
RESULTS = ROOT / "ml" / "cxr" / "results" / f"{MODEL_NAME}.json"
OUT_DIR = ROOT / "services" / "api" / "models" / "xray"
CHECK_IMAGES = 200
MAX_SCORE_DIFFERENCE = 0.01


class XrayModel(torch.nn.Module):
    """Network plus classifier as one model, with the heatmap as a second output."""

    def __init__(self, backbone, mean, scale, coef, intercept):
        super().__init__()
        self.backbone = backbone
        self.register_buffer("mean", torch.tensor(mean, dtype=torch.float32))
        self.register_buffer("scale", torch.tensor(scale, dtype=torch.float32))
        self.register_buffer("coef", torch.tensor(coef, dtype=torch.float32))
        self.register_buffer("intercept", torch.tensor(intercept, dtype=torch.float32))

    def forward(self, image):
        maps = self.backbone.forward_features(image)
        pooled = maps.mean(dim=(2, 3))
        logit = ((pooled - self.mean) / self.scale * self.coef).sum(dim=1) + self.intercept
        weights = (self.coef / self.scale)[None, :, None, None]
        return torch.sigmoid(logit), (maps * weights).sum(dim=1)


def main() -> None:
    bundle = joblib.load(CHECKPOINT)
    scaler, classifier = bundle["pipeline"].steps[0][1], bundle["pipeline"].steps[-1][1]
    backbone = timm.create_model(MODEL_NAME, pretrained=True, num_classes=0).eval()
    model = XrayModel(
        backbone, scaler.mean_, scaler.scale_, classifier.coef_[0], classifier.intercept_[0]
    ).eval()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUT_DIR / "model.onnx"
    torch.onnx.export(
        model,
        (torch.zeros(1, 3, 224, 224),),
        onnx_path,
        input_names=["image"],
        output_names=["probability", "cam"],
        dynamic_axes={"image": {0: "batch"}, "probability": {0: "batch"}, "cam": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    print(f"Exported {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB)")

    # ---- Parity check: same scores as the original, from the raw image files ----
    data = np.load(FEATURES)
    expected = bundle["pipeline"].predict_proba(data["features"])[:, 1]
    rng = np.random.default_rng(0)
    picks = rng.choice(len(expected), CHECK_IMAGES, replace=False)
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    differences, colours = [], []
    for i in picks:
        with Image.open(IMAGES / str(data["paths"][i])) as image:
            colours.append(colour_difference(image))
            score = session.run(None, {"image": preprocess(image)})[0].ravel()[0]
        differences.append(abs(float(score) - float(expected[i])))
    worst = max(differences)
    print(
        f"Parity on {CHECK_IMAGES} test images: mean difference {np.mean(differences):.5f}, "
        f"worst {worst:.5f}"
    )
    print(f"Colour difference of real X-rays: largest {max(colours):.2f}")
    if worst > MAX_SCORE_DIFFERENCE:
        onnx_path.unlink()
        raise SystemExit(f"Exported model disagrees with the original by {worst:.4f}")

    results = json.loads(RESULTS.read_text())
    test = results["test"]
    meta = {
        "version": f"{MODEL_NAME}-logreg-jutb-v1",
        "task": "xray",
        "threshold": float(bundle["threshold"]),
        "counts_towards_referral": True,
        "status": "unvalidated",
        "note": (
            "Tested only on JU-TB, which has known shortcuts (every tinted test image is TB), "
            "so real-world accuracy is likely to be lower. Not externally validated."
        ),
        "training_data": "JU-TB (cleaned exact duplicates)",
        "population": "Digital chest X-rays. Use for people aged 15 and over.",
        "test_results": {k: test[k] for k in ["n", "n_tb", "auroc", "sensitivity", "specificity"]},
    }
    (OUT_DIR / "model.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Saved {OUT_DIR / 'model.json'}")


if __name__ == "__main__":
    main()
