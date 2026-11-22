"""Who is calling? Checks the Supabase login token on each request, and the user's role.

The browser signs in with Supabase Auth and sends its access token as
"Authorization: Bearer <token>". We ask Supabase who that token belongs to, then read
the user's role from the profiles table:
- practitioner: the counter portal (screen, ABHA lookup, forward or dismiss)
- asha: the ASHA portal (cases, patients, suggestions)
- coordinator: both
Answers are cached for a minute, so most requests don't wait for Supabase.

If login isn't required (no Supabase settings, as in the tests), every check passes.
"""

import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request

from app.config import settings

CACHE_SECONDS = 60
_client = httpx.Client(timeout=10)
_cache: dict[str, tuple[float, "User"]] = {}


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: str
    full_name: str
    district: str
    place: str | None


def _secret_headers() -> dict[str, str]:
    key = settings.supabase_secret_key or ""
    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _lookup(token: str) -> User:
    """Ask Supabase Auth whose token this is, then read their profile."""
    res = _client.get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={"apikey": settings.supabase_secret_key or "", "Authorization": f"Bearer {token}"},
    )
    if res.status_code != 200:
        raise HTTPException(status_code=401, detail="Please sign in again")
    account = res.json()
    profile = _client.get(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"id": f"eq.{account['id']}", "select": "role,full_name,district,place"},
        headers=_secret_headers(),
    )
    rows = profile.json() if profile.status_code == 200 else []
    if not rows:
        raise HTTPException(status_code=403, detail="This account has no TBC² role yet")
    p = rows[0]
    return User(
        account["id"],
        account.get("email", ""),
        p["role"],
        p["full_name"],
        p["district"],
        p["place"],
    )


def current_user(request: Request) -> User | None:
    """The signed-in user, or None when login isn't required."""
    if not settings.login_required:
        return None
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    token = header[7:]
    cached = _cache.get(token)
    if cached and cached[0] > time.monotonic():
        user = cached[1]
    else:
        user = _lookup(token)
        if len(_cache) > 500:  # keep the cache small
            _cache.clear()
        _cache[token] = (time.monotonic() + CACHE_SECONDS, user)
    request.state.user = user
    return user


def require(*roles: str):
    """A FastAPI dependency: only signed-in users with one of these roles may continue."""

    def check(request: Request) -> User | None:
        user = current_user(request)
        if user is not None and user.role not in (*roles, "coordinator"):
            raise HTTPException(status_code=403, detail="Your role can't use this part of TBC²")
        return user

    return check
