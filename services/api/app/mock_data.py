"""Fake data so the front end can be built before the database is connected.

Everything lives in memory: restarting the server resets it. Later:
- everything here moves to Supabase Postgres (Mumbai region),
- risk scores come from the XGBoost model in ml/dropout,
- suggested actions come from the TBC² agent.

The journey this file simulates:
1. Counter: a pharmacist screens someone (a Screening) and may forward them.
2. ASHA: the forwarded person becomes a Case. The ASHA contacts them, collects sputum,
   books the weekly mobile X-ray van, adds the X-ray and records the NAAT result.
3. Treatment: if the NAAT confirms TB, the Medical Officer starts treatment and the
   person becomes a Patient, tracked every day.

The care-tracking parts follow the TBC² plan:
- Patients report each day's dose themselves (99DOTS style).
- The missed-dose ladder: a phone call after 3 missed days in a row,
  an ASHA visit after 7.
- Random IsoScreen urine tests check whether the self-reports are true:
  about once a month for low-risk patients, once a fortnight for high-risk ones.
  "No isoniazid found" counts as high risk. Drug-resistant regimens have no isoniazid,
  so those patients aren't tested.
"""

import hashlib
import hmac
import random
from datetime import date, datetime, time, timedelta

from app.config import settings
from app.inference.referral import decide
from app.inference.scoring import band_of
from app.schemas import (
    AbhaRecord,
    Action,
    Case,
    IsoScreenTest,
    LadderStep,
    NaatResult,
    Patient,
    RiskEntry,
    Screening,
    StartTreatmentIn,
    VanSlot,
)

# Five mostly rural districts of Karnataka. Yadgir and Raichur are NITI Aayog
# aspirational districts. The demo is set in Chamarajanagar's Hanur taluk, with
# forest-fringe and tribal villages around MM Hills and BR Hills.
DISTRICTS = {
    "Chamarajanagar": (11.92, 76.94),
    "Yadgir": (16.77, 77.14),
    "Raichur": (16.20, 77.36),
    "Koppal": (15.35, 76.15),
    "Kalaburagi": (17.33, 76.83),
}

# Made-up ASHA names and van sites. The demo district has the most.
DEMO_DISTRICT = "Chamarajanagar"
ASHAS = {
    "Chamarajanagar": ["Mahadevamma S.", "Nagamma K.", "Puttamma R."],
    "Yadgir": ["Sharanamma B."],
    "Raichur": ["Yellamma D."],
    "Koppal": ["Hanamavva G."],
    "Kalaburagi": ["Shivaleela P."],
}
VAN_SITES = {
    "Chamarajanagar": [("PHC Ramapura", 1), ("CHC Hanur", 3), ("PHC Odeyarapalya", 4)],  # 0 = Mon
    "Yadgir": [("CHC Gurmitkal", 1)],
    "Raichur": [("CHC Devadurga", 2)],
    "Koppal": [("CHC Kushtagi", 1)],
    "Kalaburagi": [("CHC Afzalpur", 3)],
}
DEMO_PRACTITIONER = "Hanur pharmacy counter"

CALL_AFTER_MISSED_DAYS = 3
VISIT_AFTER_MISSED_DAYS = 7
HIGH_RISK_SCORE = 0.6
CONTACT_WITHIN = timedelta(hours=48)

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


# ---------------------------------------------------------------- patients on treatment


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
    """Count missed days at the end of the log (up to the last recorded day)."""
    count = 0
    for day in reversed(log):
        if day != "missed":
            break
        count += 1
    return count


def _isoscreen_tests(
    rng: random.Random, days_on_treatment: int, log: list[str]
) -> list[IsoScreenTest]:
    """IsoScreen tests done so far. People who skip doses more often show no isoniazid."""
    missed_share = log.count("missed") / max(1, len(log))
    tests = []
    day = rng.randint(10, 30)  # first test falls on a random day in the first month
    while day <= days_on_treatment:
        missing = rng.random() < 0.02 + 0.4 * missed_share
        tests.append(
            IsoScreenTest(
                day_on_treatment=day,
                result="inh_not_detected" if missing else "inh_detected",
                hours_since_dose=rng.randint(8, 30),
            )
        )
        day += rng.randint(14, 30)
    return tests


def _make_patients(n: int = 60, seed: int = 7) -> dict[str, Patient]:
    rng = random.Random(seed)  # fixed seed: same patients on every restart
    # A second generator for fields added later, so the original patients stay the same.
    extra = random.Random(seed + 1)
    patients = {}
    for i in range(1, n + 1):
        district = rng.choice(list(DISTRICTS))
        # Put about a third of the patients in the demo district, so its lists aren't empty.
        if extra.random() < 0.35:
            district = DEMO_DISTRICT
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
            last_dose_logged_on=YESTERDAY,  # so today's dose can still be recorded
            missed_in_a_row=_missed_in_a_row(log),
            isoscreen_tests=_isoscreen_tests(rng, days_on_treatment, log),
            side_effect_reported=rng.random() < 0.08,
            asha_name=extra.choice(ASHAS[district]),
            phc=extra.choice(VAN_SITES[district])[0],
            weight_band=extra.choice(["35-49", "35-49", "50-64", "50-64", "65-75"]),
        )
        if p.regimen == "drug-resistant":
            p.isoscreen_tests = []  # no isoniazid in the regimen, so nothing to test
        patients[p.patient_id] = p
    return patients


def ladder_step(p: Patient) -> LadderStep:
    """Where the patient is on the missed-dose ladder today."""
    if p.missed_in_a_row >= VISIT_AFTER_MISSED_DAYS:
        return "asha_visit"
    if p.missed_in_a_row >= CALL_AFTER_MISSED_DAYS:
        return "call"
    return "on_track"


def last_inh_missing(p: Patient) -> IsoScreenTest | None:
    """The most recent IsoScreen test that found no isoniazid, if any."""
    missing = [t for t in p.isoscreen_tests if t.result == "inh_not_detected"]
    return missing[-1] if missing else None


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
    missing = last_inh_missing(p)
    if missing:
        factors.append((0.3, f"IsoScreen: no isoniazid on day {missing.day_on_treatment}"))
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
    # No isoniazid in the urine always counts as high risk, whatever the other points say.
    if missing:
        score = max(score, HIGH_RISK_SCORE)
    high_risk = score >= HIGH_RISK_SCORE
    tests_isoniazid = p.regimen == "drug-sensitive"
    return RiskEntry(
        patient=p,
        risk_score=round(score, 2),
        reasons=[reason for _, reason in factors[:3]],
        ladder_step=ladder_step(p),
        isoscreen_every_days=(14 if high_risk else 30) if tests_isoniazid else None,
        is_mock=True,
    )


def _draft_action(action_id: int, entry: RiskEntry) -> Action:
    """Stand-in for the TBC² agent: pick one next step with simple rules.

    The order matters: a side effect needs a doctor first, then the
    missed-dose ladder, then an IsoScreen test to check doubtful self-reports.
    """
    p = entry.patient
    reason = "; ".join(entry.reasons)
    asha = p.asha_name or "the ASHA"
    if p.side_effect_reported:
        kind = "side_effect_referral"
        draft = (
            f"Ask {asha} to take {p.patient_id} to the PHC Medical Officer for a "
            "side-effect review. The medicine must not be stopped without the doctor."
        )
    elif entry.ladder_step == "asha_visit" or (entry.ladder_step == "call" and not p.has_phone):
        kind = "asha_visit"
        draft = (
            f"{asha} to visit {p.patient_id} this week: no dose for {p.missed_in_a_row} days. "
            "Check for side effects, food, travel or stigma."
        )
    elif entry.ladder_step == "call" or p.regimen == "drug-resistant":
        kind = "call"
        draft = (
            "Namaskara! We noticed you haven't logged your TB medicine for "
            f"{p.missed_in_a_row} days. Is everything okay? Your ASHA can help."
            if entry.ladder_step == "call"
            else "Namaskara! A quick check-in on your TB medicine. Your ASHA can help."
        )
    else:
        kind = "isoscreen_test"
        draft = (
            f"Do an unannounced IsoScreen urine test for {p.patient_id} within 7 days "
            "to check the reported doses."
        )
    return Action(
        action_id=action_id, patient_id=p.patient_id, type=kind, reason=reason, draft=draft
    )


PATIENTS = _make_patients()

# Drafted actions for the 3 highest-risk patients in each district, all waiting for approval.
_top = [
    entry
    for district in DISTRICTS
    for entry in sorted(
        (mock_risk(p) for p in PATIENTS.values() if p.district == district),
        key=lambda e: -e.risk_score,
    )[:3]
]
ACTIONS: dict[int, Action] = {i: _draft_action(i, e) for i, e in enumerate(_top, start=1)}


def record_dose(p: Patient, status: str) -> None:
    """Add today's self-report to the end of the 28-day log."""
    p.dose_log_last_28_days = (p.dose_log_last_28_days + [status])[-28:]
    p.last_dose_logged_on = TODAY
    p.doses_missed_last_4_weeks = p.dose_log_last_28_days.count("missed")
    p.missed_in_a_row = _missed_in_a_row(p.dose_log_last_28_days)


# ---------------------------------------------------------------- ABHA (simulated)


def abha_key(abha_number: str) -> str:
    """A keyed hash of the ABHA number, so the number itself never has to be stored."""
    secret = settings.abha_hash_key.encode()
    return hmac.new(secret, abha_number.encode(), hashlib.sha256).hexdigest()


# Synthetic records for four demo ABHA numbers. There is no connection to ABDM.
ABHA_DEMO: dict[str, AbhaRecord] = {
    abha_key(number): record
    for number, record in [
        (
            "91-5528-7340-1196",
            AbhaRecord(
                abha_last4="1196",
                age=45,
                sex="M",
                district=DEMO_DISTRICT,
                history=["diabetes", "smoker"],
                conditions=["Type 2 diabetes since 2019, on metformin", "Smokes about 10 a day"],
                is_mock=True,
            ),
        ),
        (
            "91-6043-2817-5502",
            AbhaRecord(
                abha_last4="5502",
                age=63,
                sex="F",
                district=DEMO_DISTRICT,
                history=["past_tb", "underweight"],
                conditions=["Pulmonary TB in 2021, treatment completed", "BMI 17.6 at last visit"],
                is_mock=True,
            ),
        ),
        (
            "91-7712-0459-8834",
            AbhaRecord(
                abha_last4="8834",
                age=34,
                sex="F",
                district=DEMO_DISTRICT,
                history=["hiv"],
                conditions=["HIV, on antiretroviral therapy since 2022"],
                is_mock=True,
            ),
        ),
        (
            "91-3386-9021-4470",
            AbhaRecord(
                abha_last4="4470",
                age=28,
                sex="M",
                district=DEMO_DISTRICT,
                history=[],
                conditions=["No long-term conditions recorded"],
                is_mock=True,
            ),
        ),
    ]
}


# ---------------------------------------------------------------- van, counter and cases


def _make_van_slots(weeks: int = 3) -> dict[str, VanSlot]:
    """The van visits each site once a week. List the next few visits from tomorrow."""
    rng = random.Random(11)
    slots = {}
    for district, sites in VAN_SITES.items():
        for site, weekday in sites:
            first = TODAY + timedelta(days=(weekday - TODAY.weekday()) % 7 or 7)
            for week in range(weeks):
                day = first + timedelta(weeks=week)
                slot_id = f"VAN-{day:%Y%m%d}-{site.split()[-1].upper()}"
                slots[slot_id] = VanSlot(
                    slot_id=slot_id,
                    district=district,
                    site=site,
                    day=day,
                    capacity=30,
                    booked=rng.randint(4, 22) if week == 0 else rng.randint(0, 8),
                )
    return slots


VAN_SLOTS = _make_van_slots()
SCREENINGS: dict[str, Screening] = {}
CASES: dict[str, Case] = {}
MAX_SCREENINGS = 2000  # everything is in memory, so stop a public demo filling it up


def next_screening_id() -> str:
    return f"S-{len(SCREENINGS) + 1:04d}"


def next_case_id() -> str:
    return f"{400 + len(CASES) + 1:04d}"


def case_from(screening: Screening, forwarded_at: datetime, asha: str) -> Case:
    return Case(
        case_id=next_case_id(),
        screening_id=screening.screening_id,
        forwarded_at=forwarded_at,
        practitioner=screening.practitioner,
        age=screening.age,
        sex=screening.sex,
        district=screening.district,
        has_phone=screening.has_phone,
        symptoms=screening.symptoms,
        history=screening.history,
        abha_linked=screening.abha_linked,
        cough_risk=screening.cough_risk,
        counter_action=screening.recommended_action,
        counter_reasons=screening.reasons,
        asha_name=asha,
        contact_due_at=forwarded_at + CONTACT_WITHIN,
        is_mock=True,
    )


def _seed_counter_and_cases(seed: int = 5) -> None:
    """A week of made-up counter screenings, with forwarded cases at every step."""
    rng = random.Random(seed)
    symptom_pool = ["cough_over_2_weeks", "fever", "night_sweats", "weight_loss", "fatigue"]
    history_pool = ["diabetes", "smoker", "past_tb", "underweight", "household_contact"]
    now = datetime.combine(TODAY, time(10, 0))
    for _ in range(28):
        district = DEMO_DISTRICT if rng.random() < 0.75 else rng.choice(list(DISTRICTS))
        symptoms = rng.sample(symptom_pool, rng.choice([0, 0, 1, 1, 2, 3]))
        history = rng.sample(history_pool, rng.choice([0, 0, 1, 2]))
        cough_risk = round(rng.betavariate(2, 3), 2)
        step, reasons = decide(set(symptoms), set(history), False, False, cough_risk >= 0.5)
        screening = Screening(
            screening_id=next_screening_id(),
            screened_at=now - timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 8)),
            practitioner=rng.choice([DEMO_PRACTITIONER, "Ramapura clinic counter"]),
            age=rng.randint(18, 75),
            sex=rng.choice(["M", "F"]),
            district=district,
            has_phone=rng.random() < 0.85,
            symptoms=symptoms,
            history=history,
            abha_linked=rng.random() < 0.3,
            cough_risk=cough_risk,
            risk_band=band_of(cough_risk),
            recommended_action=step,
            reasons=reasons,
            is_mock=True,
        )
        if step == "routine_care":
            screening.decision, screening.dismiss_reason = "dismissed", "low_risk"
        SCREENINGS[screening.screening_id] = screening

    # Forward the demo district's screenings that need a check; move each case to its own step.
    to_forward = [
        s
        for s in sorted(SCREENINGS.values(), key=lambda s: s.screened_at)
        if s.decision == "pending" and s.district == DEMO_DISTRICT
    ]
    steps = ["on_treatment", "closed", "naat_positive", "risk_combined", "xray_done", "xray_booked",
             "xray_booked", "contacted", "not_reached", "new", "new"]  # fmt: skip
    demo_slots = sorted(
        (s for s in VAN_SLOTS.values() if s.district == DEMO_DISTRICT), key=lambda s: s.day
    )
    for screening, step in zip(to_forward, steps, strict=False):
        forwarded_at = screening.screened_at + timedelta(minutes=10)
        case = case_from(screening, forwarded_at, rng.choice(ASHAS[DEMO_DISTRICT]))
        screening.decision, screening.case_id = "forwarded", case.case_id
        CASES[case.case_id] = case
        if step == "new":
            continue
        if step == "not_reached":
            case.contact_attempts = 2
            continue
        case.contact_attempts, case.contacted_at = 1, forwarded_at + timedelta(hours=20)
        case.status = "contacted"
        if case.counter_action == "naat":
            case.sputum_collected_at = case.contacted_at
        if step == "contacted":
            continue
        case.xray_slot, case.status = demo_slots[rng.randrange(len(demo_slots))], "xray_booked"
        if step == "xray_booked":
            continue
        case.xray_source, case.xray_risk, case.status = (
            "upload",
            round(rng.uniform(0.2, 0.9), 2),
            "xray_done",
        )
        if step == "xray_done":
            continue
        case.combined_risk = max(case.xray_risk, case.cough_risk or 0)
        case.combined_band = band_of(case.combined_risk)
        case.combined_action = "naat"
        case.combined_reasons = ["Chest X-ray risk is high."]
        case.status = "risk_combined"
        if step == "risk_combined":
            continue
        case.sputum_collected_at = case.sputum_collected_at or case.contacted_at
        case.naat_attempts = 1
        if step in ("naat_positive", "on_treatment"):
            case.naat_result, case.status = "mtb_detected_rr_not_detected", "naat_positive"
            if step == "on_treatment":
                form = StartTreatmentIn(
                    mo_name="Dr. R. Nagaraj",
                    phc=case.xray_slot.site,
                    weight_band="35-49",
                    notified_in_nikshay=True,
                )
                patient = start_treatment(case, form, case.naat_result)
                # Started four days ago and has taken every dose since.
                patient.days_on_treatment = 4
                patient.dose_log_last_28_days = ["taken"] * 3
                patient.last_dose_logged_on = YESTERDAY
                case.status, case.patient_id = "on_treatment", patient.patient_id
                case.mo_name, case.notified_in_nikshay = form.mo_name, True
        else:
            case.naat_result, case.status = "mtb_not_detected", "closed"
            case.closed_reason = "NAAT: MTB not detected"

    # Older screenings nobody forwarded were declined at the counter. Today's stay open.
    for screening in SCREENINGS.values():
        if screening.decision == "pending" and screening.screened_at.date() < TODAY:
            screening.decision, screening.dismiss_reason = "dismissed", "declined"


def start_treatment(case: Case, form: StartTreatmentIn, naat: NaatResult) -> Patient:
    """Turn a confirmed case into a patient on day 0 of treatment.

    The counter answers fill in what they can (e.g. "had TB before"). Home location and
    distance to the clinic are made up, because the screen never asks for an address.
    """
    rng = random.Random(case.case_id)  # same made-up details for the same case
    lat, lon = DISTRICTS[case.district]
    number = max(int(pid.removeprefix("SYN-")) for pid in PATIENTS) + 1
    history = set(case.history)
    patient = Patient(
        patient_id=f"SYN-{number:05d}",
        age=case.age,
        sex=case.sex,
        district=case.district,
        lat=round(lat + rng.uniform(-0.15, 0.15), 4),
        lon=round(lon + rng.uniform(-0.15, 0.15), 4),
        distance_to_clinic_km=round(rng.expovariate(1 / 6), 1),
        # Rifampicin resistance means a drug-resistant regimen at the DR-TB centre.
        regimen="drug-resistant" if naat == "mtb_detected_rr_detected" else "drug-sensitive",
        days_on_treatment=0,
        doses_missed_last_4_weeks=0,
        alcohol_use="alcohol_use" in history,
        undernourished="underweight" in history,
        previously_treated="past_tb" in history,
        has_phone=case.has_phone,
        gets_nutrition_support=False,
        dose_log_last_28_days=[],  # filled in day by day from today
        missed_in_a_row=0,
        isoscreen_tests=[],
        side_effect_reported=False,
        asha_name=case.asha_name,
        phc=form.phc,
        weight_band=form.weight_band,
        case_id=case.case_id,
    )
    PATIENTS[patient.patient_id] = patient
    return patient


_seed_counter_and_cases()
