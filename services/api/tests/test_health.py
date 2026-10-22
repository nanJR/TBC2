"""Tests are practice exams the code must pass. Run them with: uv run pytest"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_says_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mock_screen_returns_valid_scores():
    response = client.post("/screen/mock")
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is True
    assert 0 <= body["risk_score"] <= 1
