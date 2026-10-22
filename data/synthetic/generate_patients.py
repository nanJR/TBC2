"""Generate fake (synthetic) TB patients for the dropout-risk model and the dashboard.

Run from the repo root:
    python data/synthetic/generate_patients.py --n 5000

Output: data/processed/synthetic_patients.csv  (git ignores this folder)

IMPORTANT, read before using the results anywhere:
- Every person here is made up. No real patient data is used.
- The numbers in PARAMS below are PLACEHOLDERS chosen to look reasonable.
  Before the report, replace each one with a figure from the India TB Report
  (or another cited source) and write the source next to it.
- Whether a patient "drops out" is decided by OUR OWN rule (see dropout_probability).
  So a model trained on this data can only learn our rule back. Its accuracy
  shows the pipeline works; it is NOT evidence of real-world performance.

Only the Python standard library is used, so this runs anywhere without installs.
"""

import argparse
import csv
import math
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings. Each value is a PLACEHOLDER until replaced with a cited figure.
# ---------------------------------------------------------------------------
PARAMS = {
    "share_male": 0.65,  # TODO: cite India TB Report (notified cases by sex)
    "share_drug_resistant": 0.05,  # TODO: cite
    "share_hiv": 0.03,  # TODO: cite
    "share_diabetes": 0.08,  # TODO: cite
    "share_alcohol_use": 0.15,  # TODO: cite
    "share_undernourished": 0.35,  # TODO: cite
    "share_previously_treated": 0.15,  # TODO: cite
    "share_has_phone": 0.80,  # TODO: cite
    "share_gets_nutrition_support": 0.60,  # TODO: cite (Ni-kshay Poshan Yojana)
}

# A few districts with approximate centre coordinates, used for the dashboard map.
DISTRICTS = {
    "Bengaluru Urban": (12.97, 77.59),
    "Tumakuru": (13.34, 77.10),
    "Mysuru": (12.30, 76.64),
    "Kolar": (13.14, 78.13),
    "Chikkaballapur": (13.43, 77.73),
}

FIELDS = [
    "patient_id",
    "age",
    "sex",
    "district",
    "lat",
    "lon",
    "distance_to_clinic_km",
    "regimen",
    "days_on_treatment",
    "doses_missed_last_4_weeks",
    "hiv",
    "diabetes",
    "alcohol_use",
    "undernourished",
    "previously_treated",
    "has_phone",
    "gets_nutrition_support",
    "dropped_out",
]


def chance(rng: random.Random, p: float) -> int:
    """Return 1 with probability p, else 0 (like flipping a weighted coin)."""
    return 1 if rng.random() < p else 0


def dropout_probability(p: dict) -> float:
    """Our made-up rule for how likely a patient is to stop treatment.

    It is a logistic formula: start from a low base, add points for each risk
    factor, then squash the total into a probability between 0 and 1.
    The weights are invented so the model has a pattern to find.
    """
    score = -3.0
    score += 0.45 * p["doses_missed_last_4_weeks"]
    score += 0.04 * p["distance_to_clinic_km"]
    score += 0.8 * p["alcohol_use"]
    score += 0.6 * p["undernourished"]
    score += 0.5 * p["previously_treated"]
    score += 0.7 * (p["regimen"] == "drug-resistant")
    score -= 0.6 * p["gets_nutrition_support"]
    score -= 0.4 * p["has_phone"]
    return 1 / (1 + math.exp(-score))


def make_patient(i: int, rng: random.Random) -> dict:
    district = rng.choice(list(DISTRICTS))
    lat, lon = DISTRICTS[district]
    regimen = "drug-resistant" if chance(rng, PARAMS["share_drug_resistant"]) else "drug-sensitive"

    patient = {
        "patient_id": f"SYN-{i:05d}",
        # Ages cluster in working years; clamp to a sensible range.
        "age": max(15, min(85, round(rng.gauss(40, 15)))),
        "sex": "M" if chance(rng, PARAMS["share_male"]) else "F",
        "district": district,
        # Spread patients a little around the district centre.
        "lat": round(lat + rng.uniform(-0.15, 0.15), 4),
        "lon": round(lon + rng.uniform(-0.15, 0.15), 4),
        "distance_to_clinic_km": round(rng.expovariate(1 / 6), 1),  # most live close, a few far
        "regimen": regimen,
        # Drug-sensitive treatment is about 6 months; drug-resistant is longer.
        "days_on_treatment": rng.randint(1, 180 if regimen == "drug-sensitive" else 540),
        "doses_missed_last_4_weeks": min(28, int(rng.expovariate(1 / 2))),
        "hiv": chance(rng, PARAMS["share_hiv"]),
        "diabetes": chance(rng, PARAMS["share_diabetes"]),
        "alcohol_use": chance(rng, PARAMS["share_alcohol_use"]),
        "undernourished": chance(rng, PARAMS["share_undernourished"]),
        "previously_treated": chance(rng, PARAMS["share_previously_treated"]),
        "has_phone": chance(rng, PARAMS["share_has_phone"]),
        "gets_nutrition_support": chance(rng, PARAMS["share_gets_nutrition_support"]),
    }
    patient["dropped_out"] = chance(rng, dropout_probability(patient))
    return patient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=5000, help="how many patients to make")
    parser.add_argument("--seed", type=int, default=42, help="same seed = same patients")
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/synthetic_patients.csv")
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    patients = [make_patient(i, rng) for i in range(1, args.n + 1)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(patients)

    rate = sum(p["dropped_out"] for p in patients) / len(patients)
    print(f"Wrote {len(patients)} patients to {args.out} (dropout rate {rate:.1%})")


if __name__ == "__main__":
    main()
