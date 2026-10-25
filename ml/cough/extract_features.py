"""Turn every cough clip into a short list of numbers that describe its sound.

Run from the ml/ folder (takes about a minute):
    uv run python cough/extract_features.py

Output: data/processed/cough_features.npz (git ignores it), one row per clip with
`features`, `labels` (1 = TB, 0 = Healthy), `person` (who coughed), `source`
(TBscreen or Coswara), `split` and `paths`.

IMPORTANT, why the clips are cleaned up first:
The TB clips and the clinic non-TB clips (TBscreen, files PID_*) are each
exactly 1 second long at 44.1 kHz. The Coswara clips (COSWARA_*), all labelled
Healthy, are 0-15 second home recordings, mostly at 48 kHz. A model could learn
"long clip = healthy" without ever hearing TB. So every clip is:
  1. resampled to the same rate (16 kHz),
  2. cut to the loudest 1-second window (Coswara) or padded to 1 second,
  3. scaled to the same peak loudness.
That removes the obvious give-aways, but NOT the microphone/room differences,
which is why train_classifier.py also reports results on TBscreen clips alone.
"""

import re
from pathlib import Path

import librosa
import numpy as np
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "Cough_Audio" / "audio_wav"
OUT_FILE = ROOT / "data" / "processed" / "cough_features.npz"
SAMPLE_RATE = 16_000  # Hz; plenty for coughs, and the lowest rate in the data
CLIP_SECONDS = 1.0
LABELS = {"Healthy": 0, "TB": 1}
MIN_SOUND_SECONDS = 0.3  # skip recordings shorter than this (some are empty)


def person_id(file_name: str) -> str:
    """Which person a clip belongs to.

    TBscreen: PID_10A114_yeti.wav -> PID_10A (person 10, cohort A, clip 114).
    Coswara:  COSWARA_<id>_cough-heavy.wav -> COSWARA_<id>.
    """
    match = re.match(r"(PID_\d+[A-Z])|(COSWARA_[^_]+)", file_name)
    if match is None:
        raise ValueError(f"Can't tell whose clip this is: {file_name}")
    return match.group(0)


def load_one_second(path: Path) -> np.ndarray | None:
    """Load a clip as exactly 1 second at 16 kHz, peak-normalised. None if too short."""
    audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    if len(audio) < MIN_SOUND_SECONDS * SAMPLE_RATE:
        return None
    n = int(CLIP_SECONDS * SAMPLE_RATE)
    if len(audio) > n:
        # Slide a 1-second window along the clip and keep the loudest part,
        # which is where the cough is. A running total makes each window's energy
        # one subtraction: energy[i] = total up to (i + n) - total up to i.
        running = np.concatenate([[0.0], np.cumsum(audio.astype(np.float64) ** 2)])
        energy = running[n:] - running[:-n]
        start = int(np.argmax(energy))
        audio = audio[start : start + n]
    else:
        audio = np.pad(audio, (0, n - len(audio)))
    peak = np.abs(audio).max()
    return audio / peak if peak > 0 else None


def describe(audio: np.ndarray) -> np.ndarray:
    """Summarise one second of sound as 168 numbers.

    - 64 mel bands: how much energy there is at each pitch range (like a spectrogram),
      summarised over time by their mean and standard deviation (128 numbers).
    - 20 MFCCs: a compact description of the sound's "shape" (timbre),
      again mean and standard deviation (40 numbers).
    """
    mel = librosa.power_to_db(librosa.feature.melspectrogram(y=audio, sr=SAMPLE_RATE, n_mels=64))
    mfcc = librosa.feature.mfcc(S=mel, n_mfcc=20)
    return np.concatenate([mel.mean(1), mel.std(1), mfcc.mean(1), mfcc.std(1)])


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
