"""One list of cough clips, whatever dataset they came from.

The trainer only sees `Clip` rows, so adding a dataset means writing one function here.
Run this file to see what a dataset contains:
    uv run python cough/manifest.py
"""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[2]
KAGGLE_DIR = ROOT / "data" / "raw" / "Cough_Audio" / "audio_wav"
CODA_DIR = ROOT / "data" / "raw" / "CODA_TB"
KAGGLE_LABELS = {"Healthy": 0, "TB": 1}


@dataclass(frozen=True)
class Clip:
    path: Path
    person: str  # all clips from one person must stay in one split
    label: int  # 1 = TB, 0 = not TB
    source: str  # where it was recorded, e.g. TBscreen, Coswara, or a CODA country
    split: str  # train, val or test
    clinical: tuple[float, ...] = ()  # routine clinical data as numbers, if the dataset has it
    groups: tuple[tuple[str, str], ...] = ()  # e.g. (("sex", "F"),), for results by group


def person_id(file_name: str) -> str:
    """Which person a Kaggle clip belongs to.

    TBscreen: PID_10A114_yeti.wav -> PID_10A (person 10, cohort A, clip 114).
    Coswara:  COSWARA_<id>_cough-heavy.wav -> COSWARA_<id>.
    """
    match = re.match(r"(PID_\d+[A-Z])|(COSWARA_[^_]+)", file_name)
    if match is None:
        raise ValueError(f"Can't tell whose clip this is: {file_name}")
    return match.group(0)


def kaggle_manifest() -> list[Clip]:
    """The Kaggle set, using its own splits."""
    clips = []
    for path in sorted(KAGGLE_DIR.glob("*/*/*.wav")):
        split, label = path.parts[-3], path.parts[-2]
        clips.append(
            Clip(
                path=path,
                person=person_id(path.name),
                label=KAGGLE_LABELS[label],
                source="Coswara" if path.name.startswith("COSWARA") else "TBscreen",
                split=split,
            )
        )
    return clips


def assign_person_splits(people: list[str], labels: list[int], seed: int = 0) -> dict[str, str]:
    """Split people into 70% train, 15% val and 15% test, keeping TB share similar.

    For datasets without their own usable split. Each person lands in exactly one split,
    because clips from one person in both train and test would inflate the score.
    """
    x = np.zeros((len(people), 1))
    y, groups = np.array(labels), np.array(people)
    folds = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=seed)
    split_of = {}
    for i, (_, held) in enumerate(folds.split(x, y, groups)):
        name = "train" if i < 14 else "val" if i < 17 else "test"
        split_of.update(dict.fromkeys(groups[held].tolist(), name))
    return split_of


def coda_manifest() -> list[Clip]:
    """CODA TB solicited coughs. TO FILL IN when the data arrives.

    Known from the challenge page:
    - CODATBSolicitedMetaInfo.csv links files in solicited_data/ to patients
      (1,082 patients, 9,772 files, 0.43 GB).
    - CODATBClinicalMetaInfo.csv holds clinical data for 1,105 patients.
    - "CODA TB Challenge data dictionary.xlsx" names the columns.

    Steps, with the real column names from the dictionary:
    1. Read both CSVs and join them on the patient ID. Keep solicited coughs only;
       longitudinal coughs are a later decision (see docs/cough-training-runbook.md).
    2. Label: microbiologically confirmed TB = 1.
    3. Splits: use assign_person_splits unless the download includes a labelled test set.
    4. clinical: only fields an ASHA can really collect, turned into numbers.
    5. groups: country, sex and HIV status, for results by group.
    """
    raise NotImplementedError(
        f"CODA TB isn't mapped yet. Put the data in {CODA_DIR}, then fill in coda_manifest() "
        "using the data dictionary."
    )


def load_manifest(dataset: str) -> list[Clip]:
    return {"kaggle": kaggle_manifest, "coda": coda_manifest}[dataset]()


if __name__ == "__main__":
    rows = kaggle_manifest()
    print(f"{len(rows)} clips from {len({r.person for r in rows})} people")
    print(Counter((r.split, r.source, r.label) for r in rows))
