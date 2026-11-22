"""Build the demo kit's media folder from the datasets on this computer.

    cd services/api && uv run python ../../demo-kit/build_demo_kit.py

1. Copies the chosen cough clips and chest X-rays from data/raw into demo-kit/media/,
   with names that say what each one shows. Git ignores demo-kit/media/: the datasets
   are CC BY 4.0 but this project never re-uploads them (see CLAUDE.md and CREDITS below).
2. Writes demo-kit/test-files/: files we make ourselves to show the error handling
   (a silent recording, a colour photo, a file that isn't audio). These are committed.

Uses only the Python standard library plus Pillow and NumPy (both in services/api).
"""

import shutil
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
KIT = ROOT / "demo-kit"

# (name in the kit, source under data/raw). Scores were checked with the served models.
MEDIA = [
    ("cough-1_TB_high-96.wav", "Cough_Audio/audio_wav/test/TB/PID_196A_42_codec.wav"),
    ("cough-2_TB_high-67.wav", "Cough_Audio/audio_wav/test/TB/PID_108A_10_codec.wav"),
    ("cough-3_TB_moderate-44.wav", "Cough_Audio/audio_wav/test/TB/PID_14A_142_codec_0.wav"),
    ("cough-4_TB_missed-1.wav", "Cough_Audio/audio_wav/test/TB/PID_8A_19_codec_0.wav"),
    ("cough-5_notTB_low-7.wav", "Cough_Audio/audio_wav/test/Healthy/PID_26C_12_codec_0.wav"),
    ("cough-6_notTB_false-alarm-91.wav", "Cough_Audio/audio_wav/test/Healthy/PID_10C_11_codec.wav"),
    ("xray-1_TB_100.jpg", "CXR/test/tb/tb184.jpg"),
    ("xray-2_TB_99.jpg", "CXR/test/tb/tb5494.jpg"),
    ("xray-3_TB_68.jpg", "CXR/test/tb/tb18989.jpg"),
    ("xray-4_normal_0.jpg", "CXR/test/Normal/normal4104.jpg"),
    ("xray-5_normal_24.jpg", "CXR/test/Normal/normal25087.jpg"),
    ("xray-6_normal_20.jpg", "CXR/test/Normal/normal25333.jpg"),
]


def copy_media() -> None:
    out = KIT / "media"
    out.mkdir(exist_ok=True)
    missing = []
    for name, source in MEDIA:
        src = RAW / source
        if src.exists():
            shutil.copyfile(src, out / name)
        else:
            missing.append(source)
    print(f"media: {len(MEDIA) - len(missing)} of {len(MEDIA)} files in {out}")
    if missing:
        print("missing (download the datasets first, see data/README.md):", *missing, sep="\n  ")


def write_wav(path: Path, samples: np.ndarray, rate: int = 16_000) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def make_test_files() -> None:
    out = KIT / "test-files"
    out.mkdir(exist_ok=True)
    # 3 seconds of silence: the API answers "too short or too quiet".
    write_wav(out / "error_silent-recording.wav", np.zeros(48_000))
    # A colourful picture, not an X-ray: the API refuses colour photos.
    x, y = np.meshgrid(np.linspace(0, 1, 400), np.linspace(0, 1, 400))
    rgb = np.stack([x, y, 1 - x], axis=-1) * 255
    Image.fromarray(rgb.astype(np.uint8)).save(out / "error_colour-photo.jpg", quality=90)
    # Text with a .wav name: the API says it can't read the cough file.
    (out / "error_not-audio.wav").write_text("This is not a sound file.\n")
    print(f"test files: 3 written to {out}")


if __name__ == "__main__":
    if not KIT.exists():
        sys.exit("Run from the repository (demo-kit/ not found).")
    copy_media()
    make_test_files()
