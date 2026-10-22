# TBC² API (FastAPI)

```bash
uv sync                       # install Python packages into .venv
uv run fastapi dev app/main.py  # start the server on http://localhost:8000
uv run pytest                 # run the tests
uv run ruff check .           # check code style
```

Open http://localhost:8000/docs to see and try every endpoint.

## Folders

- `app/main.py` — creates the app and plugs in the routers
- `app/routers/` — one file per group of endpoints (`/screen`, later `/patients`, `/risk`, `/actions`)
- `app/config.py` — settings read from `.env`
- `tests/` — pytest tests
