from fastapi.testclient import TestClient

from app.main import app
from app.mock_data import PATIENTS, ladder_step, mock_risk

client = TestClient(app)


def test_weekly_risk_is_sorted_highest_first():
    entries = client.get("/risk/weekly?limit=5").json()
    assert len(entries) == 5
    scores = [e["risk_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_unknown_patient_is_404():
    assert client.get("/patients/NOPE").status_code == 404


def test_action_can_only_be_decided_once():
    pending = client.get("/actions?status=pending").json()
    action_id = pending[0]["action_id"]

    first = client.post(f"/actions/{action_id}/approve")
    assert first.status_code == 200
    assert first.json()["status"] == "approved"

    # A decided action cannot be changed again.
    assert client.post(f"/actions/{action_id}/reject").status_code == 409


def test_missed_dose_ladder_follows_3_and_7_days():
    p = next(iter(PATIENTS.values()))
    assert ladder_step(p.model_copy(update={"missed_in_a_row": 2})) == "on_track"
    assert ladder_step(p.model_copy(update={"missed_in_a_row": 3})) == "call"
    assert ladder_step(p.model_copy(update={"missed_in_a_row": 7})) == "asha_visit"


def test_golden_check_mismatch_always_means_high_risk():
    for p in PATIENTS.values():
        entry = mock_risk(p)
        if any(c.result == "mismatch" for c in p.golden_checks):
            assert entry.risk_score >= 0.6
            assert entry.golden_check_every_days == 14


def test_every_drafted_action_starts_pending_with_a_reason():
    # Read the in-memory store directly: other tests may already have decided some.
    from app.mock_data import _draft_action, _top

    for i, entry in enumerate(_top, start=1):
        action = _draft_action(i, entry)
        assert action.status == "pending"
        assert action.reason
