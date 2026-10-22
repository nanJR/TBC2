"""Fake data so the front end can be built before the database and models exist.

Everything lives in memory: restarting the server resets it. In later weeks:
- patients come from Postgres (Supabase),
- risk scores come from the XGBoost model in ml/dropout,
- actions come from the LangGraph agent in agent/.
"""

import random

from app.schemas import Action, Patient, RiskEntry

DISTRICTS = {
    "Bengaluru Urban": (12.97, 77.59),
    "Tumakuru": (13.34, 77.10),
    "Mysuru": (12.30, 76.64),
    "Kolar": (13.14, 78.13),
    "Chikkaballapur": (13.43, 77.73),
}


def _make_patients(n: int = 60, seed: int = 7) -> dict[str, Patient]:
    rng = random.Random(seed)  # fixed seed: same patients on every restart
    patients = {}
    for i in range(1, n + 1):
        district = rng.choice(list(DISTRICTS))
        lat, lon = DISTRICTS[district]
        p = Patient(
            patient_id=f"SYN-{i:05d}",
            age=rng.randint(18, 75),
            sex=rng.choice(["M", "F"]),
            district=district,
            lat=round(lat + rng.uniform(-0.15, 0.15), 4),
            lon=round(lon + rng.uniform(-0.15, 0.15), 4),
            distance_to_clinic_km=round(rng.expovariate(1 / 6), 1),
            regimen="drug-resistant" if rng.random() < 0.05 else "drug-sensitive",
            days_on_treatment=rng.randint(1, 180),
            doses_missed_last_4_weeks=min(28, int(rng.expovariate(1 / 2))),
            alcohol_use=rng.random() < 0.15,
            undernourished=rng.random() < 0.35,
            previously_treated=rng.random() < 0.15,
            has_phone=rng.random() < 0.8,
            gets_nutrition_support=rng.random() < 0.6,
        )
        patients[p.patient_id] = p
    return patients


def mock_risk(p: Patient) -> RiskEntry:
    """Stand-in for the real model: add up points for each risk factor.

    Each reason is paired with its points so we can list the biggest first,
    the same way SHAP values will rank reasons for the real model.
    """
    factors: list[tuple[float, str]] = []
    if p.doses_missed_last_4_weeks:
        factors.append(
            (0.08 * p.doses_missed_last_4_weeks, f"missed {p.doses_missed_last_4_weeks} doses")
        )
    if p.distance_to_clinic_km > 10:
        factors.append((0.15, f"lives {p.distance_to_clinic_km:g} km from clinic"))
    if p.alcohol_use:
        factors.append((0.15, "alcohol use"))
    if p.undernourished and not p.gets_nutrition_support:
        factors.append((0.12, "undernourished, no nutrition support"))
    if p.previously_treated:
        factors.append((0.1, "treated for TB before"))
    if not p.has_phone:
        factors.append((0.08, "no phone for reminders"))

    factors.sort(reverse=True)
    score = min(0.99, 0.05 + sum(points for points, _ in factors))
    return RiskEntry(
        patient=p,
        risk_score=round(score, 2),
        reasons=[reason for _, reason in factors[:3]],
        is_mock=True,
    )


def _draft_action(action_id: int, entry: RiskEntry) -> Action:
    """Stand-in for the AI agent: pick a next step with simple rules."""
    p = entry.patient
    if not p.has_phone or p.distance_to_clinic_km > 10:
        kind, draft = "home_visit", f"Visit {p.patient_id} this week: {', '.join(entry.reasons)}."
    elif p.undernourished and not p.gets_nutrition_support:
        kind, draft = (
            "nutrition_support",
            f"Enrol {p.patient_id} for nutrition support; patient is undernourished.",
        )
    else:
        kind, draft = (
            "sms",
            "Namaskara! Please remember your TB medicine today. "
            "Call your ASHA worker if you need help.",
        )
    return Action(action_id=action_id, patient_id=p.patient_id, type=kind, draft=draft)


PATIENTS = _make_patients()

# Drafted actions for the 10 highest-risk patients, all waiting for approval.
_top = sorted((mock_risk(p) for p in PATIENTS.values()), key=lambda e: -e.risk_score)[:10]
ACTIONS: dict[int, Action] = {i: _draft_action(i, e) for i, e in enumerate(_top, start=1)}
