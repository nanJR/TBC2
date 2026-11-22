"""Entry point for the TBC² back end.

Run it with:  uv run fastapi dev app/main.py
Then open http://localhost:8000/docs to try every endpoint in the browser.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.auth import require
from app.config import settings
from app.routers import actions, cases, counter, meta, patients, screen
from app.routers.screen import MAX_REQUEST_BYTES


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load saved data from Supabase (or seed it the first time). Does nothing in memory mode.
    await run_in_threadpool(db.load_or_seed)
    yield


app = FastAPI(
    title="TBC² API",
    description="Prototype for learning only. Not for clinical use.",
    version="0.2.0",
    lifespan=lifespan,
)


# After every successful change, note who made it in the audit log (Supabase only).
@app.middleware("http")
async def audit_changes(request: Request, call_next):
    response = await call_next(request)
    user = getattr(request.state, "user", None)
    if request.method == "POST" and response.status_code < 400 and user is not None:
        path = request.url.path
        await run_in_threadpool(db.audit, user.id, user.role, f"POST {path}", path)
    return response


# Refuse oversized uploads before reading them, so one request can't fill the memory.
@app.middleware("http")
async def limit_screen_upload_size(request: Request, call_next):
    path = request.url.path
    is_upload = path == "/screen" or (path.startswith("/cases/") and path.endswith("/xray"))
    if request.method == "POST" and is_upload:
        length = request.headers.get("content-length", "")
        if not length.isdigit() or int(length) > MAX_REQUEST_BYTES:
            return JSONResponse({"detail": "Upload is too large"}, status_code=413)
    return await call_next(request)


# Let the Next.js front end call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    # One address, or several separated by commas (e.g. localhost and the Vercel site).
    # A trailing "/" is ignored: browsers send the origin without one.
    allow_origins=[o.strip().rstrip("/") for o in settings.frontend_origin.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Each router is one group of related endpoints, kept in its own file. When login is on,
# each group checks the user's role: pharmacists use the counter, ASHAs the ASHA portal.
counter_only = [Depends(require("practitioner"))]
asha_only = [Depends(require("asha"))]
app.include_router(meta.router, dependencies=[Depends(require("practitioner", "asha"))])
app.include_router(screen.router, dependencies=counter_only)
app.include_router(counter.router, dependencies=counter_only)
app.include_router(cases.router, dependencies=asha_only)
app.include_router(patients.router, dependencies=asha_only)
app.include_router(actions.router, dependencies=asha_only)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Quick check that the server is up. The front end calls this."""
    return {"status": "ok"}
