# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

TBC² is a TB care coordinator prototype (RVCE Experiential Learning, team "The MedMinds"). An ASHA phone app screens people for TB, and a district dashboard flags patients likely to drop out of treatment. It is a FastAPI back end (`services/api/`) plus a Next.js front end (`apps/web/`). `agent/` (LangGraph), `ml/cough`, `ml/cxr`, `ml/dropout`, `ml/export` and `sim/` (Mesa) are empty placeholders for now. **Prototype for learning only, not for clinical use.**

## Commands

The dev machine is WSL. Keep the repo in the Linux filesystem (`~/code/TBC2`), not under `/mnt/c`.

```bash
# services/api/  (Python 3.12+, uv)
uv sync
uv run fastapi dev app/main.py                      # http://localhost:8000/docs
uv run pytest                                       # all tests
uv run pytest tests/test_patients_and_actions.py -k <name>   # one test
uv run ruff check . && uv run ruff format --check .

# apps/web/  (Node 20+; CI uses 24)
npm install
npm run dev     # http://localhost:3000
npm run lint    # eslint
npm run build

# repo root
./scripts/dev.sh                                    # both servers, logs tagged [api]/[web]
API_PORT=8100 WEB_PORT=3100 ./scripts/dev.sh        # if 8000/3000 are taken
./scripts/tmux-dev.sh                               # tmux session "TBC2": claude, servers, lazygit
python data/synthetic/generate_patients.py --n 5000 # -> data/processed/synthetic_patients.csv (stdlib only)
```

No keys are needed: all data is in-memory mock data. `dev.sh` exports `FRONTEND_ORIGIN` (read by `app/config.py` for CORS) and `NEXT_PUBLIC_API_URL` (read by `lib/api.ts`). CI (`.github/workflows/ci.yml`) runs ruff check, ruff format --check and pytest, then `npm run lint` and `npm run build`.

## Off-limits

- Never add real patient data. Use only public research datasets or synthetic patients (`SYN-xxxxx` IDs). There is no connection to Ni-kshay or any ASHA system, and none should be added.
- Never commit datasets, model weights or `.env` / `.env.local` files. Datasets live in `data/raw/Cough_Audio/` and `data/raw/CXR/`, which git ignores. Both are CC BY 4.0, but never re-upload them; cite the authors.
- Don't strip the `nextjs-agent-rules` block from `apps/web/AGENTS.md`. `next dev` puts it back, so commit it as is.

## Invariants

- Nothing is sent without a person's approval. Agent-drafted `Action`s start as `pending`, and only `POST /actions/{id}/approve|reject` changes them, once (a second decision returns 409). Keep this rule when the real agent and SMS sending arrive.
- Update `apps/web/lib/api.ts` whenever `services/api/app/schemas.py` or `ScreenResult` in `app/routers/screen.py` changes. The TypeScript types mirror the Pydantic models by hand.
- Pages call the back end only through the helpers in `apps/web/lib/api.ts`, never with a raw `fetch()`.
- Every score response carries `is_mock`. Keep it `True` until a real model produces the number.
- Treat the rates in `generate_patients.py` as placeholders (`TODO: cite`) until they are replaced with India TB Report figures. Dropout labels come from our own rule, so model accuracy on synthetic data only shows the pipeline works. Never report it as real-world performance.
- Next.js here is 16.4 with React 19.3 (`cacheComponents` and `partialPrefetching` on). Read `apps/web/node_modules/next/dist/docs/` before writing Next.js code. Don't rely on memory.
- Write comments in the existing style: plain language aimed at beginner teammates, explaining what the code does and why.

## Architecture

`services/api/app/main.py` adds CORS for `settings.frontend_origin` and registers one router per file in `app/routers/`:
- `screen.py` → `POST /screen/mock` returns a fixed cough/X-ray score and their average. The real models will go in `app/inference/`.
- `patients.py` → `/patients`, `/patients/{id}` and `/risk/weekly?limit=` (sorted highest risk first).
- `actions.py` → `/actions?status=` and approve/reject.

`app/mock_data.py` stands in for every future data source. It builds 60 seeded patients (in place of Supabase Postgres, `DATABASE_URL`), uses `mock_risk()` (rule points ranked like SHAP reasons, in place of the XGBoost model in `ml/dropout`) and holds an `ACTIONS` dict (in place of the LangGraph agent). State lives in memory and resets when the server restarts. Tests use `TestClient(app)` and import `app.main` (pytest `pythonpath = ["."]`).

`apps/web` uses the App Router with route groups: `app/(asha)/screen` (the ASHA PWA flow, `app/manifest.ts`) and `app/(district)/dashboard` (risk table plus approve/reject). Both are client components. The UI uses shadcn/ui (`base-nova` style on `@base-ui/react`) in `components/ui` and Tailwind v4 through the `@tailwindcss/turbopack` loader.

## Glossary

| Term | Meaning → code |
| --- | --- |
| TBC² | The project name ("TB care coordinator") |
| ASHA | Accredited Social Health Activist, a community health worker → `app/(asha)/screen` |
| District team | Officials who review risk and approve actions → `app/(district)/dashboard` |
| Ni-kshay | India's national TB patient system. We never connect to it |
| Ni-kshay Poshan Yojana | Government nutrition support for TB patients → `gets_nutrition_support`, `nutrition_support` action |
| CXR | Chest X-ray → `xray_score`, `ml/cxr` |
| Grad-CAM | Heatmap of where the X-ray model looked (planned) |
| Dropout / loss to follow-up | A patient stopping treatment → `/risk/weekly`, `ml/dropout` |
| SHAP | Per-feature explanation of the dropout score → `RiskEntry.reasons` |
| Drug-sensitive / drug-resistant | TB regimen types → `Patient.regimen` |
| TBscreen / Coswara | Clinic TB and non-TB coughs (`PID_*`) / crowdsourced healthy coughs (`COSWARA_*`) → `data/raw/Cough_Audio` |
| JU-TB | 55k TB/Normal chest X-ray set → `data/raw/CXR` |
