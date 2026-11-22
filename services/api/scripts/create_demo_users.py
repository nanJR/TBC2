"""Create (or reset) the three demo accounts in Supabase Auth and give them roles.

Run from services/api after filling in .env (SUPABASE_URL, SUPABASE_SECRET_KEY,
DEMO_PASSWORD_PRACTITIONER, DEMO_PASSWORD_ASHA, DEMO_PASSWORD_COORDINATOR):

    uv run python scripts/create_demo_users.py

The addresses use example.com, a domain reserved for examples, and are confirmed
directly, so no email is ever sent. Passwords come from .env and are never printed.
"""

import os
import sys

import httpx

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402

ACCOUNTS = [
    {
        "email": "counter.hanur@example.com",
        "password_env": "DEMO_PASSWORD_PRACTITIONER",
        "profile": {
            "role": "practitioner",
            "full_name": "Pharmacist",
            "district": "Chamarajanagar",
            "place": "Hanur",
        },
    },
    {
        # The admin login: a coordinator can use both portals.
        "email": "coordinator.tbc2@example.com",
        "password_env": "DEMO_PASSWORD_COORDINATOR",
        "profile": {
            "role": "coordinator",
            "full_name": "District TB Coordinator",
            "district": "Chamarajanagar",
            "place": "District TB Centre",
        },
    },
    {
        "email": "asha.hanur@example.com",
        "password_env": "DEMO_PASSWORD_ASHA",
        "profile": {
            "role": "asha",
            "full_name": "Mahadevamma S.",
            "district": "Chamarajanagar",
            "place": "Hanur",
        },
    },
]


def env(name: str) -> str:
    # .env is read by pydantic-settings for the app; read it here too for the passwords.
    if name in os.environ:
        return os.environ[name]
    for line in open(".env").read().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"Missing {name} in .env")


def main() -> None:
    if not settings.supabase_enabled:
        sys.exit("Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env first.")
    key = settings.supabase_secret_key
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    base = settings.supabase_url
    with httpx.Client(timeout=20, headers=headers) as http:
        existing = http.get(f"{base}/auth/v1/admin/users", params={"per_page": 200})
        existing.raise_for_status()
        by_email = {u["email"]: u["id"] for u in existing.json().get("users", [])}
        for account in ACCOUNTS:
            password = env(account["password_env"])
            if len(password) < 12:
                sys.exit(f"{account['password_env']} must be at least 12 characters.")
            if account["email"] in by_email:
                user_id = by_email[account["email"]]
                http.put(
                    f"{base}/auth/v1/admin/users/{user_id}", json={"password": password}
                ).raise_for_status()
                action = "updated"
            else:
                res = http.post(
                    f"{base}/auth/v1/admin/users",
                    json={"email": account["email"], "password": password, "email_confirm": True},
                )
                res.raise_for_status()
                user_id, action = res.json()["id"], "created"
            http.post(
                f"{base}/rest/v1/profiles",
                params={"on_conflict": "id"},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                json={"id": user_id, **account["profile"]},
            ).raise_for_status()
            print(f"{action}: {account['email']} ({account['profile']['role']})")


if __name__ == "__main__":
    main()
