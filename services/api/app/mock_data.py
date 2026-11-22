"""Fake data so the front end can be built before the database and models exist.

Everything lives in memory: restarting the server resets it. In later weeks:
- patients come from Postgres (Supabase),
- risk scores come from the XGBoost model in ml/dropout,
- actions come from the LangGraph agent.

The care-tracking parts follow the TBC² plan:
- Patients report each day's dose themselves (99DOTS style).
- The missed-dose ladder: a phone call after 3 missed days in a row,
  an ASHA visit after 7.
- Random urine "golden checks" test whether the self-reports are true:
  about once a month for low-risk patients, once a fortnight for high-risk ones.
  A mismatch (reported "taken", urine says no) counts as high risk.
"""

import random

from app.schemas import Action, GoldenCheck, LadderStep, Patient, RiskEntry

DISTRICTS = {
    "Bengaluru Urban": (12.97, 77.59),
    "Tumakuru": (13.34, 77.10),
    "Mysuru": (12.30, 76.64),
    "Kolar": (13.14, 78.13),
    "Chikkaballapur": (13.43, 77.73),
}

CALL_AFTER_MISSED_DAYS = 3
VISIT_AFTER_MISSED_DAYS = 7
HIGH_RISK_SCORE = 0.6


def _dose_log(rng: random.Random, days_on_treatment: int) -> list[str]:
    """Make the last 28 days of self-reports for one patient, oldest first.

    Each patient gets one of three made-up patterns, so the dashboard shows
    a mix: most take their medicine, some slip now and then, a few stop.
    """
    days = min(28, days_on_treatment)
    pattern = rng.choices(["steady", "slipping", "stopping"], weights=[64, 18, 18])[0]
    if pattern == "steady":
        log = ["missed" if rng.random() < 0.03 else "taken" for _ in range(days)]
    elif pattern == "slipping":
        log = ["missed" if rng.random() < 0.25 else "taken" for _ in range(days)]
    else:
        # Took doses, then stopped some days ago and has not restarted.
        stopped_days_ago = min(days, rng.randint(3, 12))
        log = ["taken"] * (days - stopped_days_ago) + ["missed"] * stopped_days_ago
    return log


def _missed_in_a_row(log: list[str]) -> int:
    """Count missed days at the end of the log (up to today)."""
    count = 0
    for day in reversed(log):
        if day != "missed":
            break
        count += 1
    return count


def _golden_checks(rng: random.Random, days_on_treatment: int, log: list[str]) -> list[GoldenCheck]:
    """Urine checks done so far. People who skip doses are more likely to mismatch."""
    missed_share = log.count("missed") / max(1, len(log))
    checks = []
    day = rng.randint(10, 30)  # first check falls on a random day in the first month
    while day <= days_on_treatment:
        mismatch = rng.random() < 0.02 + 0.4 * missed_share
        checks.append(GoldenCheck(day_on_treatment=day, result="mismatch" if mismatch else "match"))
        day += rng.randint(14, 30)
    return checks


def _make_patients(n: int = 60, seed: int = 7) -> dict[str, Patient]:
    rng = random.Random(seed)  # fixed seed: same patients on every restart
    patients = {}
    for i in range(1, n + 1):
        district = rng.choice(list(DISTRICTS))
        lat, lon = DISTRICTS[district]
        days_on_treatment = rng.randint(7, 180)
        log = _dose_log(rng, days_on_treatment)
        p = Patient(
            patient_id=f"SYN-{i:05d}",
            age=rng.randint(18, 75),
            sex=rng.choice(["M", "F"]),
            district=district,
            lat=round(lat + rng.uniform(-0.15, 0.15), 4),
            lon=round(lon + rng.uniform(-0.15, 0.15), 4),
            distance_to_clinic_km=round(rng.expovariate(1 / 6), 1),
            regimen="drug-resistant" if rng.random() < 0.05 else "drug-sensitive",
            days_on_treatment=days_on_treatment,
            doses_missed_last_4_weeks=log.count("missed"),
            alcohol_use=rng.random() < 0.15,
            undernourished=rng.random() < 0.35,
            previously_treated=rng.random() < 0.15,
            has_phone=rng.random() < 0.8,
            gets_nutrition_support=rng.random() < 0.6,
            dose_log_last_28_days=log,
            missed_in_a_row=_missed_in_a_row(log),
            golden_checks=_golden_checks(rng, days_on_treatment, log),
            side_effect_reported=rng.random() < 0.08,
        )
        patients[p.patient_id] = p
    return patients


def ladder_step(p: Patient) -> LadderStep:
    """Where the patient is on the missed-dose ladder today."""
    if p.missed_in_a_row >= VISIT_AFTER_MISSED_DAYS:
        return "asha_visit"
    if p.missed_in_a_row >= CALL_AFTER_MISSED_DAYS:
        return "call"
    return "on_track"


def last_mismatch(p: Patient) -> GoldenCheck | None:
    """The most recent golden check that did not match, if any."""
    mismatches = [c for c in p.golden_checks if c.result == "mismatch"]
    return mismatches[-1] if mismatches else None


def mock_risk(p: Patient) -> RiskEntry:
    """Stand-in for the real model: add up points for each risk factor.

    Each reason is paired with its points so we can list the biggest first,
    the same way SHAP values will rank reasons for the real model.
    """
    factors: list[tuple[float, str]] = []
    if p.missed_in_a_row >= CALL_AFTER_MISSED_DAYS:
        factors.append((0.1 * p.missed_in_a_row, f"no dose for {p.missed_in_a_row} days"))
    elif p.doses_missed_last_4_weeks:
        factors.append(
            (
                0.04 * p.doses_missed_last_4_weeks,
                f"missed {p.doses_missed_last_4_weeks} of 28 doses",
            )
        )
    mismatch = last_mismatch(p)
    if mismatch:
        factors.append((0.3, f"golden check mismatch on day {mismatch.day_on_treatment}"))
    if p.side_effect_reported:
        factors.append((0.2, "reported a side effect"))
    if p.distance_to_clinic_km > 10:
        factors.append((0.12, f"lives {p.distance_to_clinic_km:g} km from clinic"))
    if p.alcohol_use:
        factors.append((0.12, "alcohol use"))
    if p.undernourished and not p.gets_nutrition_support:
        factors.append((0.1, "undernourished, no nutrition support"))
    if p.previously_treated:
        factors.append((0.08, "treated for TB before"))
    if not p.has_phone:
        factors.append((0.06, "no phone for reminders"))

    factors.sort(reverse=True)
    score = min(0.99, 0.05 + sum(points for points, _ in factors))
    # A mismatch always counts as high risk, whatever the other points say.
    if mismatch:
        score = max(score, HIGH_RISK_SCORE)
    high_risk = score >= HIGH_RISK_SCORE
    return RiskEntry(
        patient=p,
        risk_score=round(score, 2),
        reasons=[reason for _, reason in factors[:3]],
        ladder_step=ladder_step(p),
        golden_check_every_days=14 if high_risk else 30,
        is_mock=True,
    )


def _draft_action(action_id: int, entry: RiskEntry) -> Action:
    """Stand-in for the AI agent: pick one next step with simple rules.

    The order matters: a side effect needs a doctor first, then the
    missed-dose ladder, then a golden check to test doubtful self-reports.
    """
    p = entry.patient
    reason = "; ".join(entry.reasons)
    if p.side_effect_reported:
        kind = "side_effect_referral"
        draft = (
            f"Ask the simulated ASHA to take {p.patient_id} to the PHC medical officer "
            "for a side-effect review. Do not stop the medicine without the doctor."
        )
    elif entry.ladder_step == "asha_visit" or (entry.ladder_step == "call" and not p.has_phone):
        kind = "asha_visit"
        draft = (
            f"Simulated ASHA to visit {p.patient_id} this week: no dose for "
            f"{p.missed_in_a_row} days. Check for side effects, food, travel or stigma."
        )
    elif entry.ladder_step == "call":
        kind = "call"
        draft = (
            "Namaskara! We noticed you haven't logged your TB medicine for "
            f"{p.missed_in_a_row} days. Is everything okay? Your ASHA can help."
        )
    else:
        kind = "golden_check"
        draft = (
            f"Schedule an unannounced urine check for {p.patient_id} within 7 days "
            "to confirm the self-reported doses."
        )
    return Action(
        action_id=action_id, patient_id=p.patient_id, type=kind, reason=reason, draft=draft
    )


PATIENTS = _make_patients()

# Drafted actions for the 10 highest-risk patients, all waiting for approval.
_top = sorted((mock_risk(p) for p in PATIENTS.values()), key=lambda e: -e.risk_score)[:10]
ACTIONS: dict[int, Action] = {i: _draft_action(i, e) for i, e in enumerate(_top, start=1)}
