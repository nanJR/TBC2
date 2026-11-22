"""Decide what should happen next for the person being screened.

The order here follows India's programme and WHO, not our models:
- Anyone with a TB symptom goes for a NAAT, whatever a model says (TB Mukt Bharat
  Abhiyaan 2026, p. 8; WHO target product profiles 2025).
- An abnormal X-ray also means NAAT.
- A vulnerable person with no symptoms is offered an X-ray, because about a third of
  people diagnosed in the campaign had no symptoms.

So a model can ADD a referral but can never cancel one. No person in our data has both
a cough and an X-ray, which means this combined rule has never been tested.

The cough model is experimental (it doesn't count towards referral), so it gets one
small job: if it flags a cough, it can suggest an X-ray to double-check. An X-ray only
means more checking, so the harm is low. It can never send anyone to a NAAT on its own.
"""

from typing import Literal

Symptom = Literal[
    "cough_over_2_weeks",
    "cough_under_2_weeks",
    "fever",
    "night_sweats",
    "coughing_blood",
    "chest_pain",
    "shortness_of_breath",
    "weight_loss",
    "loss_of_appetite",
    "fatigue",
    "lymph_node_swelling",
]

Vulnerability = Literal[
    "over_60",
    "underweight",  # BMI under 18.5
    "diabetes",
    "hiv",
    "smoker",
    "alcohol_use",
    "past_tb",
    "household_contact",
]

NextStep = Literal["naat", "offer_xray", "routine_care"]


def is_presumptive(symptoms: set[str], vulnerabilities: set[str]) -> bool:
    """True if the symptoms alone mean this person should be tested.

    A cough only counts after 2 weeks, unless the person is vulnerable, when any cough
    counts. Every other listed symptom counts straight away.
    """
    other = symptoms - {"cough_under_2_weeks"}
    return bool(other) or ("cough_under_2_weeks" in symptoms and bool(vulnerabilities))


def decide(
    symptoms: set[str],
    vulnerabilities: set[str],
    xray_flagged: bool,
    xray_scored: bool,
    cough_flagged: bool = False,
) -> tuple[NextStep, list[str]]:
    """Return the next step and the plain-language reasons for it."""
    reasons = []
    if is_presumptive(symptoms, vulnerabilities):
        reasons.append("Presumptive TB: symptoms that need a NAAT test.")
    if xray_flagged:
        reasons.append("Chest X-ray risk is high.")
    if reasons:
        return "naat", reasons

    # No NAAT yet. Without an X-ray result, see if one should be offered.
    if not xray_scored:
        if vulnerabilities:
            reasons.append("In a high-risk group, with no chest X-ray yet.")
        if cough_flagged:
            reasons.append("Cough analysis shows raised TB risk. An X-ray will double-check.")
        if reasons:
            return "offer_xray", reasons
        return "routine_care", ["No TB symptoms, high-risk group or raised cough risk."]
    return "routine_care", ["No symptoms that need a test, and the chest X-ray risk is low."]


def rescale(score: float, threshold: float) -> float:
    """Stretch a score so that the model's own threshold sits at exactly 0.5.

    Each model has a different threshold, so raw scores can't be compared directly.
    """
    if score <= threshold:
        return 0.5 * score / threshold if threshold > 0 else 0.5
    return 0.5 + 0.5 * (score - threshold) / (1 - threshold)
