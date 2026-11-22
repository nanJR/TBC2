"""Login and roles: pharmacists use the counter, ASHAs the ASHA portal.

Supabase isn't called here: the token lookup is replaced by a fake that knows two users.
"""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.auth import User
from app.config import settings
from app.main import app

client = TestClient(app)

USERS = {
    "pharmacist-token": User(
        "u1", "counter@demo", "practitioner", "Pharmacist", "Chamarajanagar", "Hanur"
    ),
    "asha-token": User("u2", "asha@demo", "asha", "Mahadevamma S.", "Chamarajanagar", "Hanur"),
}


@pytest.fixture(autouse=True)
def login_on(monkeypatch):
    """Turn login on, with a fake Supabase that knows the two tokens above."""
    monkeypatch.setattr(settings, "supabase_url", "https://example.invalid")
    monkeypatch.setattr(settings, "supabase_secret_key", "test-secret")
    monkeypatch.setattr(settings, "require_login", True)
    monkeypatch.setattr(auth, "_cache", {})

    def fake_lookup(token: str) -> User:
        if token not in USERS:
            raise auth.HTTPException(status_code=401, detail="Please sign in again")
        return USERS[token]

    monkeypatch.setattr(auth, "_lookup", fake_lookup)
    # Don't try to save to the fake Supabase.
    monkeypatch.setattr("app.db.settings", type("Off", (), {"supabase_enabled": False})())


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(path, headers=headers)


def test_requests_without_a_login_are_refused():
    assert get("/cases").status_code == 401
    assert get("/screenings").status_code == 401
    assert get("/cases", "made-up-token").status_code == 401


def test_each_role_only_reaches_its_own_portal():
    assert get("/screenings", "pharmacist-token").status_code == 200
    assert get("/cases", "pharmacist-token").status_code == 403
    assert get("/risk/weekly", "pharmacist-token").status_code == 403
    assert get("/cases", "asha-token").status_code == 200
    assert get("/screenings", "asha-token").status_code == 403


def test_both_roles_share_the_overview_and_districts():
    for token in USERS:
        assert get("/overview", token).status_code == 200
        assert get("/districts", token).status_code == 200


def test_me_tells_the_front_end_who_is_signed_in():
    body = get("/me", "asha-token").json()
    assert body == {
        "signed_in": True,
        "email": "asha@demo",
        "role": "asha",
        "full_name": "Mahadevamma S.",
        "district": "Chamarajanagar",
        "place": "Hanur",
    }


def test_health_needs_no_login():
    assert get("/health").status_code == 200
