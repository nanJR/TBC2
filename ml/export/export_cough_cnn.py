"""Pack a network from cough/train_cnn.py into model.onnx and model.json.

Run from the ml/ folder:
    uv run python export/export_cough_cnn.py --name cough_only --out ../services/api/models/cough

The model always starts with counts_towards_referral false. That only changes by hand, after
the checks in docs/cough-training-runbook.md, so a new model can't quietly affect referrals.
It stops with an error if the exported model disagrees with the original.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "cough"))
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.inference.audio import load_one_second, log_mel
from manifest import load_manifest
from train_cnn import CHECKPOINT_DIR, CoughNet

CHECK_CLIPS = 20
MAX_SCORE_DIFFERENCE = 0.001


class Exported(torch.nn.Module):
    """Ends in a 0-1 score. Without clinical data it takes only the picture."""

    def __init__(self, net: CoughNet, clinical_size: int):
        super().__init__()
        self.net = net
        self.clinical_size = clinical_size

    def forward(self, mel, clinical=None):
        if clinical is None:
            clinical = torch.zeros(mel.shape[0], self.clinical_size)
        return torch.sigmoid(self.net(mel, clinical))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    saved = torch.load(CHECKPOINT_DIR / f"cough_cnn_{args.name}_best.pt", map_location="cpu")
    config = saved["config"]
    size = config["clinical_size"]
    net = CoughNet(config["backbone"], size, pretrained=False)
    net.load_state_dict(saved["model"])
    model = Exported(net, size).eval()

    args.out.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out / "model.onnx"
    mel = torch.zeros(1, 1, 64, 32)
    inputs = (mel, torch.zeros(1, size)) if size else (mel,)
    names = ["mel", "clinical"] if size else ["mel"]
    torch.onnx.export(
        model,
        inputs,
        onnx_path,
        input_names=names,
        output_names=["probability"],
        dynamic_axes={**{n: {0: "batch"} for n in names}, "probability": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    clips = load_manifest(config["dataset"])
    picks = np.random.default_rng(0).choice(len(clips), CHECK_CLIPS, replace=False)
    worst = 0.0
    for i in picks:
        audio = load_one_second(clips[i].path)
        if audio is None:
            continue
        picture = log_mel(audio)[None, None]
        feeds = {"mel": picture}
        if size:
            feeds["clinical"] = np.zeros((1, size), dtype=np.float32)
        exported = float(session.run(None, feeds)[0].ravel()[0])
        with torch.inference_mode():
            original = float(model(torch.from_numpy(picture), torch.zeros(1, size)).ravel()[0])
        worst = max(worst, abs(exported - original))
    print(f"Parity on {CHECK_CLIPS} clips: worst difference {worst:.6f}")
    if worst > MAX_SCORE_DIFFERENCE:
        onnx_path.unlink()
        raise SystemExit(f"Exported model disagrees with the original by {worst:.4f}")

    meta = {
        "version": f"cnn-{args.name}-{config['backbone']}",
        "task": "cough",
        "input_kind": "log_mel_clinical" if size else "log_mel",
        "threshold": float(saved["threshold"]),
        "counts_towards_referral": False,
        "status": "experimental",
        "note": "Experimental cough model, shown for information only.",
        "training_data": config["dataset"],
    }
    (args.out / "model.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
