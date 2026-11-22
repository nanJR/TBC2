"""Counter screening → manual forward → ASHA case steps → treatment → daily tracking."""

import copy

import pytest
from fastapi.testclient import TestClient

from app import mock_data
from app.main import app

client = TestClient(app)

PERSON = {"age": 40, "sex": "F", "district": "Chamarajanagar", "symptoms": ["cough_over_2_weeks"]}


@pytest.fixture(autouse=True)
def clean_store():
    """Undo everything a test adds or changes, so tests don't affect each other."""
    stores = [mock_data.SCREENINGS, mock_data.CASES, mock_data.PATIENTS, mock_data.VAN_SLOTS]
    saved = [copy.deepcopy(store) for store in stores]
    yield
    for store, before in zip(stores, saved, strict=True):
        store.clear()
        store.update(before)


def screen(cough_wav=None, **changes):
    files = {"cough": ("c.wav", cough_wav, "audio/wav")} if cough_wav else None
    return client.post("/screen", data={**PERSON, **changes}, files=files).json()


def forwarded_case(**changes) -> dict:
    screening_id = screen(**changes)["screening_id"]
    return client.post(f"/screenings/{screening_id}/forward", json={"consent_contact": True}).json()


def step(case_id, name, body=None, files=None):
    url = f"/cases/{case_id}/{name}"
    return client.post(url, files=files) if files else client.post(url, json=body)


def demo_slot() -> str:
    return client.get("/van-slots?district=Chamarajanagar").json()[0]["slot_id"]


# ---------------------------------------------------------------- ABHA


def test_abha_needs_consent_and_a_known_number():
    number = {"abha_number": "91-5528-7340-1196"}
    assert client.post("/abha/lookup", json={**number, "consent": False}).status_code == 403
    unknown = {"abha_number": "99-9999-9999-9999", "consent": True}
    assert client.post("/abha/lookup", json=unknown).status_code == 404
    bad = {"abha_number": "12345", "consent": True}
    assert client.post("/abha/lookup", json=bad).status_code == 422
    record = client.post("/abha/lookup", json={**number, "consent": True}).json()
    assert record["history"] == ["diabetes", "smoker"]
    assert record["abha_last4"] == "1196"


def test_abha_numbers_are_kept_only_as_keyed_hashes():
    assert "91-5528-7340-1196" not in mock_data.ABHA_DEMO
    assert all(len(key) == 64 for key in mock_data.ABHA_DEMO)


# ---------------------------------------------------------------- counter decisions


def test_screening_is_saved_with_cough_risk_but_no_files(tiny_models, cough_wav):
    body = screen(cough_wav)
    saved = mock_data.SCREENINGS[body["screening_id"]]
    assert saved.cough_risk is not None and saved.risk_band is not None
    assert saved.decision == "pending"
    assert "cough" not in saved.model_dump()


def test_forwarding_needs_contact_consent_and_happens_once():
    screening_id = screen()["screening_id"]
    url = f"/screenings/{screening_id}/forward"
    assert client.post(url, json={"consent_contact": False}).status_code == 403
    case = client.post(url, json={"consent_contact": True}).json()
    assert case["status"] == "new" and case["asha_name"] in mock_data.ASHAS["Chamarajanagar"]
    assert client.post(url, json={"consent_contact": True}).status_code == 409
    dismiss = client.post(f"/screenings/{screening_id}/dismiss", json={"reason": "declined"})
    assert dismiss.status_code == 409


def test_dismiss_records_the_reason():
    screening_id = screen()["screening_id"]
    body = client.post(f"/screenings/{screening_id}/dismiss", json={"reason": "low_risk"}).json()
    assert body["decision"] == "dismissed" and body["dismiss_reason"] == "low_risk"


# ---------------------------------------------------------------- ASHA case steps


def test_full_journey_from_counter_to_daily_tracking(tiny_models, xray_png):
    case_id = forwarded_case()["case_id"]
    # First call doesn't reach them: still "new", one attempt counted.
    case = step(case_id, "contact", {"reached": False}).json()
    assert case["status"] == "new" and case["contact_attempts"] == 1
    case = step(case_id, "contact", {"reached": True}).json()
    assert case["status"] == "contacted"
    # Presumptive TB: sputum goes to the lab at first contact, before the van comes.
    assert step(case_id, "sputum").json()["sputum_collected_at"] is not None
    assert step(case_id, "schedule", {"slot_id": demo_slot()}).json()["status"] == "xray_booked"
    files = {"xray": ("x.png", xray_png, "image/png")}
    case = step(case_id, "xray", files=files).json()
    assert case["status"] == "xray_done" and case["xray_risk"] is not None
    case = step(case_id, "combine").json()
    assert case["combined_action"] == "naat" and case["combined_risk"] is not None
    # Inconclusive: a fresh sample is needed before the repeat test.
    case = step(case_id, "naat", {"result": "inconclusive"}).json()
    assert case["sputum_collected_at"] is None
    assert step(case_id, "naat", {"result": "inconclusive"}).status_code == 409
    step(case_id, "sputum")
    case = step(case_id, "naat", {"result": "mtb_detected_rr_not_detected"}).json()
    assert case["status"] == "naat_positive"
    treatment = {"mo_name": "Dr. Demo", "phc": "PHC Ramapura", "weight_band": "50-64"}
    case = step(case_id, "start-treatment", treatment).json()
    assert case["status"] == "on_treatment"
    patient = client.get(f"/patients/{case['patient_id']}").json()
    assert patient["regimen"] == "drug-sensitive" and patient["days_on_treatment"] == 0
    # Daily tracking: one dose entry a day.
    url = f"/patients/{case['patient_id']}/doses"
    assert client.post(url, json={"status": "taken"}).status_code == 200
    assert client.post(url, json={"status": "taken"}).status_code == 409


def test_rifampicin_resistance_means_a_drug_resistant_regimen():
    case = forwarded_case()
    case_id = case["case_id"]
    step(case_id, "contact", {"reached": True})
    step(case_id, "sputum")
    step(case_id, "naat", {"result": "mtb_detected_rr_detected"})
    treatment = {"mo_name": "Dr. Demo", "phc": "PHC Ramapura", "weight_band": "35-49"}
    patient_id = step(case_id, "start-treatment", treatment).json()["patient_id"]
    assert mock_data.PATIENTS[patient_id].regimen == "drug-resistant"
    isoscreen = client.post(f"/patients/{patient_id}/isoscreen", json={"result": "inh_detected"})
    assert isoscreen.status_code == 422


def test_steps_out_of_order_are_refused():
    case_id = forwarded_case()["case_id"]
    assert step(case_id, "combine").status_code == 409
    assert step(case_id, "sputum").status_code == 409  # not contacted yet
    treatment = {"mo_name": "Dr. Demo", "phc": "PHC Ramapura", "weight_band": "50-64"}
    assert step(case_id, "start-treatment", treatment).status_code == 409
    step(case_id, "contact", {"reached": True})
    assert step(case_id, "naat", {"result": "mtb_not_detected"}).status_code == 409  # no sample


def test_symptoms_still_mean_naat_after_a_normal_van_reading():
    case_id = forwarded_case()["case_id"]
    step(case_id, "contact", {"reached": True})
    step(case_id, "schedule", {"slot_id": demo_slot()})
    step(case_id, "van-reading", {"reading": "normal"})
    assert step(case_id, "combine").json()["combined_action"] == "naat"


def test_a_clear_xray_without_symptoms_ends_in_routine_care():
    case_id = forwarded_case(symptoms=[])["case_id"]
    step(case_id, "contact", {"reached": True})
    step(case_id, "schedule", {"slot_id": demo_slot()})
    step(case_id, "van-reading", {"reading": "normal"})
    assert step(case_id, "combine").json()["combined_action"] == "routine_care"
    assert step(case_id, "close", {"reason": "xray_clear"}).json()["status"] == "closed"


def test_van_slots_must_be_in_the_district_and_not_full():
    case_id = forwarded_case()["case_id"]
    step(case_id, "contact", {"reached": True})
    other = client.get("/van-slots?district=Raichur").json()[0]["slot_id"]
    assert step(case_id, "schedule", {"slot_id": other}).status_code == 404
    slot_id = demo_slot()
    mock_data.VAN_SLOTS[slot_id].booked = mock_data.VAN_SLOTS[slot_id].capacity
    assert step(case_id, "schedule", {"slot_id": slot_id}).status_code == 409


def test_overview_counts_each_step():
    before = client.get("/overview?district=Chamarajanagar").json()
    forwarded_case()
    after = client.get("/overview?district=Chamarajanagar").json()
    assert after["screened"] == before["screened"] + 1
    assert after["forwarded"] == before["forwarded"] + 1
    assert after["awaiting_contact"] == before["awaiting_contact"] + 1
