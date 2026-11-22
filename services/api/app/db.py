"""Keep the in-memory stores (app/mock_data.py) saved in Supabase Postgres.

How it works:
- At startup, load_or_seed() reads every table. An empty table is filled with the
  synthetic seed data; otherwise the saved rows replace the seed, so changes made in
  the portals survive a server restart.
- After every change, the routers call save_*(), which upserts that one record.
- Every successful change made by a signed-in user is written to audit_log.

All calls use the server-only secret key, which bypasses row-level security; browsers
can't reach these tables at all (see supabase/migrations/). If Supabase isn't
configured, every function here does nothing and the app runs in memory.

Only the REST API (PostgREST) is used, over plain HTTPS, so no database password or
extra driver is needed.
"""

import logging
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel

from app import mock_data
from app.config import settings
from app.schemas import AbhaRecord, Action, Case, Patient, Screening, VanSlot

log = logging.getLogger("tbc2.db")
_client = httpx.Client(timeout=15)

# table name → (in-memory store, model class, how to read id/district/status)
STORES = {
    "screenings": (
        mock_data.SCREENINGS,
        Screening,
        lambda s: (s.screening_id, s.district, s.decision),
    ),
    "cases": (mock_data.CASES, Case, lambda c: (c.case_id, c.district, c.status)),
    "patients": (mock_data.PATIENTS, Patient, lambda p: (p.patient_id, p.district, p.regimen)),
    "actions": (
        mock_data.ACTIONS,
        Action,
        lambda a: (str(a.action_id), mock_data.PATIENTS[a.patient_id].district, a.status),
    ),
    "van_slots": (mock_data.VAN_SLOTS, VanSlot, lambda v: (v.slot_id, v.district, "open")),
}


def _headers() -> dict[str, str]:
    key = settings.supabase_secret_key or ""
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # an older JWT-style service_role key also needs this header
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _rest(table: str) -> str:
    return f"{settings.supabase_url}/rest/v1/{table}"


def _upsert(table: str, rows: list[dict]) -> None:
    if not settings.supabase_enabled or not rows:
        return
    try:
        res = _client.post(
            _rest(table),
            params={"on_conflict": "id" if table != "abha_records" else "abha_hash"},
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=rows,
        )
        res.raise_for_status()
    except httpx.HTTPError as error:
        # Keep the app working (the change is still in memory) but make the failure visible.
        log.error("Could not save to Supabase table %s: %s", table, error)


def _row(table: str, record: BaseModel) -> dict:
    _, _, keys = STORES[table]
    row_id, district, status = keys(record)
    return {
        "id": row_id,
        "district": district,
        "status": status,
        "data": record.model_dump(mode="json"),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def save(table: str, *records: BaseModel) -> None:
    """Upsert one or more records into a table."""
    _upsert(table, [_row(table, r) for r in records])


def save_screening(s: Screening) -> None:
    save("screenings", s)


def save_case(c: Case) -> None:
    save("cases", c)


def save_patient(p: Patient) -> None:
    save("patients", p)


def save_action(a: Action) -> None:
    save("actions", a)


def save_slot(v: VanSlot) -> None:
    save("van_slots", v)


def audit(actor_id: str | None, actor_role: str | None, action: str, path: str) -> None:
    """One line per change: who did what, and when (the database adds the time)."""
    if not settings.supabase_enabled:
        return
    parts = [p for p in path.split("/") if p]
    row = {
        "actor": actor_id,
        "actor_role": actor_role,
        "action": action,
        "table_name": parts[0] if parts else "",
        "row_id": parts[1] if len(parts) > 1 else None,
    }
    try:
        _client.post(
            _rest("audit_log"), headers={**_headers(), "Prefer": "return=minimal"}, json=row
        ).raise_for_status()
    except httpx.HTTPError as error:
        log.error("Could not write the audit log: %s", error)


def _load(table: str) -> list[dict]:
    res = _client.get(_rest(table), params={"select": "data", "limit": "10000"}, headers=_headers())
    res.raise_for_status()
    return [row["data"] for row in res.json()]


def load_or_seed() -> None:
    """Fill the in-memory stores from Supabase, or seed Supabase from them the first time."""
    if not settings.supabase_enabled:
        return
    for table, (store, model, _) in STORES.items():
        rows = _load(table)
        if not rows:
            save(table, *store.values())
            log.info("Seeded Supabase table %s with %d rows", table, len(store))
            continue
        store.clear()
        for data in rows:
            record = model.model_validate(data)
            key = STORES[table][2](record)[0]
            store[int(key) if table == "actions" else key] = record
        log.info("Loaded %d rows from Supabase table %s", len(rows), table)

    # The ABHA demo registry: only keyed hashes of the numbers are stored.
    records = _load_abha()
    if records:
        mock_data.ABHA_DEMO.clear()
        mock_data.ABHA_DEMO.update(records)
    else:
        _upsert(
            "abha_records",
            [
                {"abha_hash": h, "data": r.model_dump(mode="json")}
                for h, r in mock_data.ABHA_DEMO.items()
            ],
        )


def _load_abha() -> dict[str, AbhaRecord]:
    res = _client.get(
        _rest("abha_records"), params={"select": "abha_hash,data"}, headers=_headers()
    )
    res.raise_for_status()
    return {row["abha_hash"]: AbhaRecord.model_validate(row["data"]) for row in res.json()}
