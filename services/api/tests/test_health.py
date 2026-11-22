"""Tests are practice exams the code must pass. Run them with: uv run pytest"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_says_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_is_the_same_check_as_health():
    # The website uses /status, because some ad blockers block URLs containing "health".
    assert client.get("/status").json() == {"status": "ok"}
