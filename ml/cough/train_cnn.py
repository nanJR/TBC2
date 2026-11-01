"""Train a cough network on log-mel pictures, ready for CODA TB and a GPU.

Run from the ml/ folder:
    uv run python cough/train_cnn.py --smoke                    # proves the code works, on CPU
    uv run python cough/train_cnn.py --dataset coda --name cough_only
    uv run python cough/train_cnn.py --dataset coda --name with_clinical --with-clinical

The rules, which come from what went wrong in earlier cough studies:
- Scores are per PERSON: a person's score is the average of their clip scores.
- Every person counts equally, however many clips they have, and both classes count equally.
- The threshold is set on val to catch at least 90% of TB people. Test is scored once, at the end.
- Results are also reported by source and by group (country, sex, HIV) when known.
- With --dataset coda, the Kaggle TBscreen people are scored as an outside test. First check
  that they aren't also in CODA (see docs/cough-training-runbook.md).

--smoke results mean nothing, so they are never saved to cough/results/.
Safe to stop and rerun: it continues from checkpoints/cough_cnn_<name>_last.pt.

Output (git ignores checkpoints): checkpoints/cough_cnn_<name>_best.pt, cough/results/cnn_<name>.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn.functional as F
from manifest import Clip, load_manifest
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
from train_classifier import per_person, sample_weights

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.inference.audio import load_one_second, log_mel

from evaluation import TARGET_SENSITIVITY, pick_threshold, report

CHECKPOINT_DIR = ROOT / "ml" / "checkpoints"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
SMOKE_CLINICAL_SIZE = 4  # fake clinical numbers, only to prove that path runs


class CoughNet(torch.nn.Module):
    """A pretrained image network looking at the log-mel picture, plus optional clinical numbers."""

    def __init__(self, backbone: str, clinical_size: int, pretrained: bool = True):
        super().__init__()
        self.backbone = timm.create_model(
            backbone, pretrained=pretrained, in_chans=1, num_classes=0
        )
        # Networks report their output size differently, so measure it with a blank picture.
        self.backbone.eval()
        with torch.no_grad():
            size = self.backbone(torch.zeros(1, 1, 128, 128)).shape[1]
        self.head = torch.nn.Sequential(
            torch.nn.Dropout(0.2),
            torch.nn.Linear(size + clinical_size, 1),
        )

    def forward(self, mel: torch.Tensor, clinical: torch.Tensor) -> torch.Tensor:
        # Stretch the 64 x 32 picture so the network's many shrinking layers have room to work.
        picture = F.interpolate(mel, size=(128, 128), mode="bilinear", align_corners=False)
        return self.head(torch.cat([self.backbone(picture), clinical], dim=1)).squeeze(1)


class Prepared:
    """All usable clips in memory as arrays. Works for the solicited coughs, which are small."""

    def __init__(self, clips: list[Clip], clinical_size: int):
        kept, mels = [], []
        for clip in tqdm(clips, desc="Preparing clips", unit="clip"):
            audio = load_one_second(clip.path)
            if audio is not None:
                kept.append(clip)
                mels.append(log_mel(audio))
        self.clips = kept
        self.mel = torch.from_numpy(np.stack(mels))[:, None]
        clinical = np.zeros((len(kept), clinical_size), dtype=np.float32)
        if clinical_size and kept[0].clinical:
            clinical = np.array([c.clinical for c in kept], dtype=np.float32)
        self.clinical = torch.from_numpy(clinical)
        self.label = np.array([c.label for c in kept], dtype=np.int64)
        self.person = np.array([c.person for c in kept])
        self.source = np.array([c.source for c in kept])
        self.split = np.array([c.split for c in kept])

    def where(self, mask: np.ndarray) -> TensorDataset:
        index = torch.from_numpy(np.flatnonzero(mask))
        return TensorDataset(self.mel[index], self.clinical[index], index)


@torch.inference_mode()
def clip_scores(model, data: Prepared, mask, device, batch_size) -> np.ndarray:
    model.eval()
    scores = []
    for mel, clinical, _ in DataLoader(data.where(mask), batch_size=batch_size):
        scores.append(torch.sigmoid(model(mel.to(device), clinical.to(device))).cpu().numpy())
    return np.concatenate(scores)


def person_scores(model, data: Prepared, mask, device, batch_size):
    scores = clip_scores(model, data, mask, device, batch_size)
    return per_person(scores, data.label[mask], data.person[mask], data.source[mask])


def safe_report(labels, scores, threshold) -> dict | None:
    """A group with only one class has no AUROC, so it can't be reported."""
    if len(labels) == 0 or len(set(labels.tolist())) < 2:
        return None
    return report(labels, scores, threshold)


def by_group(model, data: Prepared, mask, device, batch_size, threshold) -> dict:
    """Results for each value of each group, such as sex=F or country=India."""
    results = {}
    names = {name for clip in data.clips for name, _ in clip.groups}
    for name in sorted(names):
        values = np.array([dict(c.groups).get(name, "unknown") for c in data.clips])
        for value in sorted(set(values[mask].tolist())):
            labels, scores, _ = person_scores(
                model, data, mask & (values == value), device, batch_size
            )
            results[f"{name}={value}"] = safe_report(labels, scores, threshold)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default="kaggle", choices=["kaggle", "coda"])
    parser.add_argument("--name", default="smoke", help="names the checkpoint and results files")
    parser.add_argument("--backbone", default="efficientnet_b0", help="any timm model name")
    parser.add_argument("--with-clinical", action="store_true")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--wandb", action="store_true", help="also log to Weights & Biases")
    parser.add_argument("--smoke", action="store_true", help="a few steps on a tiny network")
    args = parser.parse_args()

    if args.smoke:
        args.name, args.dataset, args.backbone = "smoke", "kaggle", "mobilenetv3_small_050"
        args.epochs, args.batch_size, args.workers = 2, 16, 0

    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    clips = load_manifest(args.dataset)
    clinical_size = 0
    if args.with_clinical:
        clinical_size = len(clips[0].clinical) or (SMOKE_CLINICAL_SIZE if args.smoke else 0)
        if not clinical_size:
            raise SystemExit("This dataset has no clinical data in its manifest.")
    if args.smoke:
        # About 40 people per split are enough to prove every step runs.
        keep = {
            s: sorted({c.person for c in clips if c.split == s})[::4]
            for s in ("train", "val", "test")
        }
        clips = [c for c in clips if c.person in keep[c.split]]
    data = Prepared(clips, clinical_size)
    train, val, test = (data.split == s for s in ("train", "val", "test"))

    model = CoughNet(args.backbone, clinical_size).to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)
    weights = torch.from_numpy(
        sample_weights(data.label[train], data.person[train]).astype(np.float32)
    )
    labels = torch.from_numpy(data.label.astype(np.float32))

    CHECKPOINT_DIR.mkdir(exist_ok=True)
    last_path = CHECKPOINT_DIR / f"cough_cnn_{args.name}_last.pt"
    best_path = CHECKPOINT_DIR / f"cough_cnn_{args.name}_best.pt"
    start_epoch, best_auroc = 0, -1.0
    if last_path.exists() and not args.smoke:
        saved = torch.load(last_path, map_location=device)
        model.load_state_dict(saved["model"])
        optimiser.load_state_dict(saved["optimiser"])
        scheduler.load_state_dict(saved["scheduler"])
        start_epoch, best_auroc = saved["epoch"] + 1, saved["best_auroc"]
        print(f"Continuing from epoch {start_epoch}")

    run = None
    if args.wandb:
        import wandb

        run = wandb.init(project="tbc2-cough", name=args.name, config=vars(args))

    config = {
        "backbone": args.backbone,
        "clinical_size": clinical_size,
        "dataset": args.dataset,
        "smoke": args.smoke,
    }
    # Maps a clip's position in the whole dataset to its position in the training weights.
    train_position = np.full(len(data.clips), -1)
    train_position[train] = np.arange(train.sum())
    for epoch in range(start_epoch, args.epochs):
        model.train()
        total = 0.0
        loader = DataLoader(
            data.where(train), batch_size=args.batch_size, shuffle=True, num_workers=args.workers
        )
        for mel, clinical, index in tqdm(loader, desc=f"Epoch {epoch + 1}", leave=False):
            logits = model(mel.to(device), clinical.to(device))
            loss = F.binary_cross_entropy_with_logits(
                logits,
                labels[index].to(device),
                weight=weights[train_position[index.numpy()]].to(device),
            )
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total += loss.item()
        scheduler.step()

        val_scores, val_labels, _ = person_scores(model, data, val, device, args.batch_size)
        auroc = roc_auc_score(val_labels, val_scores)
        print(f"Epoch {epoch + 1}: loss {total / len(loader):.3f}, val AUROC (people) {auroc:.3f}")
        if run:
            run.log({"epoch": epoch, "loss": total / len(loader), "val_auroc": auroc})
        if auroc > best_auroc:
            best_auroc = auroc
            torch.save({"model": model.state_dict(), "config": config}, best_path)
        torch.save(
            {
                "model": model.state_dict(),
                "optimiser": optimiser.state_dict(),
                "scheduler": scheduler.state_dict(),
                "epoch": epoch,
                "best_auroc": best_auroc,
            },
            last_path,
        )

    # ---- Everything is fixed now: threshold on val, then look at test once ----
    best = torch.load(best_path, map_location=device)
    model.load_state_dict(best["model"])
    val_scores, val_labels, _ = person_scores(model, data, val, device, args.batch_size)
    threshold = pick_threshold(val_labels, val_scores, TARGET_SENSITIVITY)

    test_scores, test_labels, test_source = person_scores(
        model, data, test, device, args.batch_size
    )
    results = {
        "dataset": args.dataset,
        "backbone": args.backbone,
        "with_clinical": args.with_clinical,
        "threshold": threshold,
        "val": safe_report(val_labels, val_scores, threshold),
        "test": safe_report(test_labels, test_scores, threshold),
        "test_by_source": {
            source: safe_report(
                test_labels[test_source == source], test_scores[test_source == source], threshold
            )
            for source in sorted(set(test_source.tolist()))
        },
        "test_by_group": by_group(model, data, test, device, args.batch_size, threshold),
    }
    if args.dataset == "coda" and not args.with_clinical:
        outside = Prepared(
            [c for c in load_manifest("kaggle") if c.source == "TBscreen"], clinical_size
        )
        everyone = np.ones(len(outside.clips), dtype=bool)
        scores, outside_labels, _ = person_scores(model, outside, everyone, device, args.batch_size)
        results["external_tbscreen"] = safe_report(outside_labels, scores, threshold)

    best["threshold"] = threshold
    torch.save(best, best_path)
    print(json.dumps({k: results[k] for k in ("threshold", "val", "test")}, indent=2))
    if args.smoke:
        print("Smoke run finished. These numbers mean nothing and were not saved to results.")
        return
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"cnn_{args.name}.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
