from fastapi.testclient import TestClient

from app.main import app

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
