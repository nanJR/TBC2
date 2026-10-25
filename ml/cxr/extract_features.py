"""Turn every chest X-ray into a list of numbers ("features") with a pretrained network.

Why: training a whole CNN on 46k images takes hours per epoch on our laptop
CPUs. Instead we run each image through an ImageNet-pretrained network ONCE,
keep its second-to-last layer (1,280 numbers per image for efficientnet_b0),
and later train a small, fast classifier on those numbers.

Run from the ml/ folder (takes a while on CPU; progress bar shows how long):
    uv run python cxr/extract_features.py
    uv run python cxr/extract_features.py --model efficientnet_b0 --batch-size 32

Output: data/processed/cxr_features/<model>/<split>.npz, which git ignores.
Each file holds `features` (one row per image), `labels` (1 = TB, 0 = Normal)
and `paths` (so any score can be traced back to its image).
Images listed in cxr/exclude.txt (duplicates) are skipped.
"""

import argparse
from pathlib import Path

import numpy as np
import timm
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "CXR"
EXCLUDE_FILE = Path(__file__).resolve().parent / "exclude.txt"
OUT_DIR = ROOT / "data" / "processed" / "cxr_features"
SPLITS = ["train", "val", "test"]
LABELS = {"Normal": 0, "tb": 1}


def list_images(split: str) -> list[tuple[Path, int]]:
    """All (image path, label) pairs in one split, minus the excluded duplicates."""
    excluded = set(EXCLUDE_FILE.read_text().split())
    items = []
    for folder, label in LABELS.items():
        for path in sorted((DATA_DIR / split / folder).glob("*.jpg")):
            if path.relative_to(DATA_DIR).as_posix() not in excluded:
                items.append((path, label))
    return items


class XrayDataset(Dataset):
    def __init__(self, items: list[tuple[Path, int]], transform):
        self.items = items
        self.transform = transform

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int):
        path, label = self.items[i]
        # convert("RGB"): the network expects 3 colour channels, even for grey X-rays.
        image = Image.open(path).convert("RGB")
        return self.transform(image), label


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="efficientnet_b0", help="any timm model name")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=2, help="image-loading processes")
    args = parser.parse_args()

    # num_classes=0 removes the ImageNet output layer, so the model returns features.
    model = timm.create_model(args.model, pretrained=True, num_classes=0).eval()
    # Resize and normalise images exactly the way this model was trained.
    config = timm.data.resolve_data_config({}, model=model)
    # ...except don't crop: the default cuts off the image edges, where lung tops sit.
    config["crop_pct"] = 1.0
    transform = timm.data.create_transform(**config)

    out_dir = OUT_DIR / args.model
    out_dir.mkdir(parents=True, exist_ok=True)

    for split in SPLITS:
        out_file = out_dir / f"{split}.npz"
        if out_file.exists():
            print(f"{out_file} already exists, skipping (delete it to redo)")
            continue

        items = list_images(split)
        loader = DataLoader(
            XrayDataset(items, transform), batch_size=args.batch_size, num_workers=args.workers
        )
        chunks = []
        with torch.inference_mode():  # no training here, so skip gradient bookkeeping
            for images, _ in tqdm(loader, desc=split, unit="batch"):
                chunks.append(model(images).numpy())

        np.savez(
            out_file,
            features=np.concatenate(chunks).astype(np.float32),
            labels=np.array([label for _, label in items], dtype=np.int8),
            paths=np.array([p.relative_to(DATA_DIR).as_posix() for p, _ in items]),
        )
        print(f"Saved {len(items)} images -> {out_file}")


if __name__ == "__main__":
    main()
