"""Turn a cough recording into numbers. Training and serving both use this file.

Keeping one copy matters: if the server prepared sound differently from training,
the model's scores would quietly become wrong.

Why clips are cleaned up first:
The clinic clips (TBscreen, files PID_*) are exactly 1 second at 44.1 kHz. The Coswara
clips (COSWARA_*), all labelled Healthy, are 0-15 second home recordings, mostly at
48 kHz. A model could learn "long clip = healthy" without ever hearing TB. So every
clip is resampled to 16 kHz, cut to its loudest second (or padded) and scaled to the
same peak loudness.
"""

from pathlib import Path
from typing import BinaryIO

import librosa
import numpy as np

SAMPLE_RATE = 16_000  # Hz; plenty for coughs, and the lowest rate in the data
CLIP_SECONDS = 1.0
MIN_SOUND_SECONDS = 0.3  # recordings shorter than this are treated as empty


def load_one_second(source: Path | BinaryIO) -> np.ndarray | None:
    """Load a clip as exactly 1 second at 16 kHz, peak-normalised. None if too short."""
    audio, _ = librosa.load(source, sr=SAMPLE_RATE, mono=True)
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
