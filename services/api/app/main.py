"""Entry point for the TBC² back end.

Run it with:  uv run fastapi dev app/main.py
Then open http://localhost:8000/docs to try every endpoint in the browser.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import actions, patients, screen

app = FastAPI(
    title="TBC² API",
    description="Prototype for learning only. Not for clinical use.",
    version="0.1.0",
)

# Let the Next.js front end call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Each router is one group of related endpoints, kept in its own file.
app.include_router(screen.router)
app.include_router(patients.router)
app.include_router(actions.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Quick check that the server is up. The front end calls this."""
    return {"status": "ok"}
