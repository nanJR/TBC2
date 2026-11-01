"""Turn every cough clip into a short list of numbers that describe its sound.

Run from the ml/ folder (takes about a minute):
    uv run python cough/extract_features.py

Output: data/processed/cough_features.npz (git ignores it), one row per clip with
`features`, `labels` (1 = TB, 0 = Healthy), `person` (who coughed), `source`
(TBscreen or Coswara), `split` and `paths`.

The clip clean-up lives in services/api/app/inference/audio.py, so that training and
the server prepare sound in exactly the same way. It removes the obvious give-aways
between clinic and home recordings, but NOT the microphone/room differences, which is
why train_classifier.py also reports results on TBscreen clips alone.
"""

import sys
from pathlib import Path

import numpy as np
from manifest import person_id
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.inference.audio import describe, load_one_second

DATA_DIR = ROOT / "data" / "raw" / "Cough_Audio" / "audio_wav"
OUT_FILE = ROOT / "data" / "processed" / "cough_features.npz"
LABELS = {"Healthy": 0, "TB": 1}


def main() -> None:
    rows = []
    skipped = 0
    paths = sorted(DATA_DIR.glob("*/*/*.wav"))
    for path in tqdm(paths, unit="clip"):
        split, label = path.parts[-3], path.parts[-2]
        audio = load_one_second(path)
        if audio is None:
            skipped += 1
            continue
        rows.append(
            {
                "features": describe(audio),
                "label": LABELS[label],
                "person": person_id(path.name),
                "source": "Coswara" if path.name.startswith("COSWARA") else "TBscreen",
                "split": split,
                "path": path.relative_to(DATA_DIR).as_posix(),
            }
        )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        OUT_FILE,
        features=np.stack([r["features"] for r in rows]).astype(np.float32),
        labels=np.array([r["label"] for r in rows], dtype=np.int8),
        person=np.array([r["person"] for r in rows]),
        source=np.array([r["source"] for r in rows]),
        split=np.array([r["split"] for r in rows]),
        paths=np.array([r["path"] for r in rows]),
    )
    print(f"Saved {len(rows)} clips -> {OUT_FILE} (skipped {skipped} too-short clips)")


if __name__ == "__main__":
    main()
