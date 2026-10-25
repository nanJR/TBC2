"""Find X-ray images that appear more than once and list the copies to skip.

Why: JU-TB has exact copies of the same image, some in different splits.
If a test image also sits in train, the model has already seen it and the
test score looks better than it really is.

Run from the ml/ folder:
    uv run python cxr/find_duplicates.py

Output: cxr/exclude.txt, one image path per line (relative to data/raw/CXR).
Nothing in data/raw is deleted; the training scripts just skip these files.

Rules:
- Two files are "the same" if their bytes are identical (same MD5 hash).
- If copies of one image have different labels (TB and Normal), we can't
  trust either label, so every copy is skipped.
- Otherwise we keep one copy, in the earliest split (train, then val,
  then test), and skip the rest. So val and test never share an image
  with train, and test never shares one with val.
"""

import hashlib
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "CXR"
OUT_FILE = Path(__file__).resolve().parent / "exclude.txt"
SPLITS = ["train", "val", "test"]  # earlier split wins when copies are found


def md5_of(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main() -> None:
    # hash -> every file with those exact bytes
    groups: dict[str, list[Path]] = defaultdict(list)
    images = sorted(DATA_DIR.glob("*/*/*.jpg"))
    print(f"Hashing {len(images)} images in {DATA_DIR} ...")
    for path in images:
        groups[md5_of(path)].append(path.relative_to(DATA_DIR))

    excluded: list[Path] = []
    contradictory = 0
    for copies in groups.values():
        if len(copies) == 1:
            continue
        labels = {p.parts[1] for p in copies}  # parts = (split, label, file)
        if len(labels) > 1:
            contradictory += 1
            excluded.extend(copies)
            continue
        copies.sort(key=lambda p: (SPLITS.index(p.parts[0]), p.name))
        excluded.extend(copies[1:])  # keep the first, skip the rest

    excluded.sort()
    OUT_FILE.write_text("".join(f"{p.as_posix()}\n" for p in excluded))

    # Summary, so the numbers can be copied into data/README.md.
    dup_groups = sum(1 for c in groups.values() if len(c) > 1)
    print(f"Duplicate groups: {dup_groups} ({contradictory} labelled both TB and Normal)")
    print(f"Excluded files: {len(excluded)} -> {OUT_FILE.name}")
    skip = {p.as_posix() for p in excluded}
    print("Cleaned split sizes:")
    for split in SPLITS:
        counts = {}
        for label in ["tb", "Normal"]:
            files = (DATA_DIR / split / label).glob("*.jpg")
            counts[label] = sum(1 for f in files if f.relative_to(DATA_DIR).as_posix() not in skip)
        print(f"  {split:5}  tb {counts['tb']:6}  Normal {counts['Normal']:6}")


if __name__ == "__main__":
    main()
