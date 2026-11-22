# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

TBC² (TB Care Coordinator) is a prototype by the team "The MedMinds". A **counter portal** lets a pharmacist or local practitioner screen a person (ABHA history, symptoms, a cough recording) and forward them by hand to an ASHA. The **ASHA portal** follows each case from first contact through the mobile X-ray van, a combined risk score and the NAAT to treatment, then tracks daily doses, IsoScreen urine tests and dropout risk. The demo is set in rural Chamarajanagar (Hanur taluk), Karnataka. It is a FastAPI back end (`services/api/`) plus a Next.js front end (`apps/web/`). `ml/` is a uv project for model training (`ml/cxr` and `ml/cough` are in progress, sharing metrics in `ml/evaluation.py`); `agent/` (LangGraph), `ml/dropout`, `ml/export` and `sim/` (Mesa) are still empty placeholders. The dev laptop has no CUDA GPU and WSL gets ~4 GB RAM, so training code must run on CPU in modest memory. **Prototype for learning only, not for clinical use.**

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

# ml/  (one uv project for all model training; CPU-only PyTorch by default)
uv sync                                             # on a CUDA machine, first drop the pytorch-cpu [tool.uv.sources] lines
uv run python cxr/find_duplicates.py                # rewrites cxr/exclude.txt; every CXR script must skip those files
uv run python cxr/extract_features.py               # ~1.5 h on CPU, resumable; then cxr/train_classifier.py
uv run python cough/extract_features.py             # ~30 s; then cough/train_classifier.py
uv run python export/export_cxr.py                  # writes services/api/models/xray; also export_cough.py
uv run python cough/train_cnn.py --smoke            # proves the CODA/GPU trainer runs; see docs/cough-training-runbook.md

# repo root
./scripts/dev.sh                                    # both servers, logs tagged [api]/[web]
API_PORT=8100 WEB_PORT=3100 ./scripts/dev.sh        # if 8000/3000 are taken
./scripts/tmux-dev.sh                               # tmux session "TBC2": claude, servers, lazygit
python data/synthetic/generate_patients.py --n 5000 # -> data/processed/synthetic_patients.csv (stdlib only)
```

**Supabase (optional).** With `SUPABASE_SECRET_KEY` in `services/api/.env` and the two `NEXT_PUBLIC_SUPABASE_*` values in `apps/web/.env.local` (see the `.env.example` files), data is saved in Supabase project TBC2 (Mumbai) and login is required. Without them, everything runs in memory with no login (this is how tests and CI run). Schema and grants: `supabase/migrations/`. Demo accounts: `cd services/api && uv run python scripts/create_demo_users.py` (passwords live only in `.env`). `dev.sh` exports `FRONTEND_ORIGIN` (read by `app/config.py` for CORS) and `NEXT_PUBLIC_API_URL` (read by `lib/api.ts`). CI (`.github/workflows/ci.yml`) runs ruff check, ruff format --check and pytest, then `npm run lint` and `npm run build`.

## Off-limits

- Never add real patient data. Use only public research datasets or synthetic patients (`SYN-xxxxx` IDs). There is no connection to Ni-kshay or any ASHA system, and none should be added.
- Never commit datasets, model weights or `.env` / `.env.local` files. Datasets live in `data/raw/Cough_Audio/` and `data/raw/CXR/`, which git ignores. Both are CC BY 4.0, but never re-upload them; cite the authors.
- Don't strip the `nextjs-agent-rules` block from `apps/web/AGENTS.md`. `next dev` puts it back, so commit it as is.

## Invariants

- Nothing is sent without a person's approval. Agent-drafted `Action`s start as `pending`, and only `POST /actions/{id}/approve|reject` changes them, once (a second decision returns 409). Keep this rule when the real agent and SMS sending arrive.
- Update `apps/web/lib/api.ts` whenever `services/api/app/schemas.py` or `ScreenResult` in `app/routers/screen.py` changes. The TypeScript types mirror the Pydantic models by hand.
- Pages call the back end only through the helpers in `apps/web/lib/api.ts`, never with a raw `fetch()`.
- Cough results must include the TBscreen-only numbers. Coswara clips are all Healthy and recorded at home, so mixed-source scores are inflated (shortcut-check AUROC 0.99). Score per person, never per clip.
- Every score response carries `is_mock`. Keep it `True` until a real model produces the number.
- A model can add a TB referral but never cancel one. Symptoms always go to NAAT (`app/inference/referral.py`), following the TB Mukt Bharat Abhiyaan and WHO. A model only affects referral if its `model.json` has `counts_towards_referral: true`. One exception: the experimental cough model may add an `offer_xray` suggestion (an X-ray to double-check), never a NAAT.
- Uploads (`/screen`, `/cases/{id}/xray`) are held in memory and never stored. Only answers and scores are saved (a `Screening`, then a `Case`). Forwarding to an ASHA is always the practitioner's manual decision and needs the person's contact consent; ABHA lookups need consent and only a keyed hash of the number is kept (`abha_key()`). Case steps run in order and each refuses with 409 when the case isn't at that step. Prepare images and sound only through `app/inference/image.py` and `audio.py`; training imports the same code, and the export scripts check that scores match.
- JU-TB leaks its labels: every tinted test image is TB, and image size tracks the label. Quote X-ray results within these groups too (grey images alone: 88.1% sensitivity). The outside test is much weaker (Shenzhen AUROC 0.78, Montgomery 0.67; see `data/README.md`), so never present the JU-TB number alone.
- Treat the rates in `generate_patients.py` as placeholders (`TODO: cite`) until they are replaced with India TB Report figures. Dropout labels come from our own rule, so model accuracy on synthetic data only shows the pipeline works. Never report it as real-world performance.
- Next.js here is 16.4 with React 19.3 (`cacheComponents` and `partialPrefetching` on). Read `apps/web/node_modules/next/dist/docs/` before writing Next.js code. Don't rely on memory.
- Supabase security: only the back end touches data tables, with the server-only secret key (never in the front end or git). Row-level security is forced on every table and browser roles (anon, authenticated) have no grants except reading their own `profiles` row; `service_role` has no DELETE and `audit_log` is append-only. New tables need RLS and explicit `service_role` grants (this project grants nothing by default). Run the Supabase security advisor after schema changes.
- Every router has a role check (`app/auth.py` `require`, wired in `main.py`): practitioners use the counter, ASHAs the ASHA portal, coordinators both. Successful POSTs by a signed-in user are written to `audit_log`.
- Write comments in the existing style: plain language aimed at beginner teammates, explaining what the code does and why.

## Architecture

`services/api/app/main.py` adds CORS for `settings.frontend_origin`, limits upload size, and registers one router per file in `app/routers/`:
- `screen.py` → `POST /screen` (the counter check): age, sex, district, symptoms, history, a WAV cough (and optionally an X-ray). Returns the next step, reasons, scores and `risk_score`/`risk_band`, and saves a `Screening` summary. Scoring lives in `app/inference/scoring.py` (`score_cough`, `score_xray`, `risk_of` rescales so each model's threshold is 0.5, `band_of`: low < 0.35 ≤ moderate < 0.5 ≤ high). Models load from `MODEL_DIR/{xray,cough}/` as `model.onnx` plus `model.json` (`app/inference/registry.py`), made by `ml/export/`. Git ignores them, and a missing model just leaves its score empty.
- `counter.py` → `POST /abha/lookup` (simulated, 4 synthetic records, consent required), `/screenings`, and `POST /screenings/{id}/forward|dismiss` (once).
- `cases.py` → `/cases`, `/van-slots`, `/overview` (patient-journey counts), and the case steps `contact → sputum → schedule → xray | van-reading → combine → naat → start-treatment` (plus `close`). `combine` takes the higher rescaled cough/X-ray score (a simple rule, not fusion) and re-runs `decide()`.
- `patients.py` → `/districts`, `/patients`, `/risk/weekly?limit=&district=`, `POST /patients/{id}/doses` (once a day) and `/isoscreen` (drug-sensitive regimens only).
- `actions.py` → `/actions?status=` and approve/reject (TBC² suggestions).

`app/db.py` mirrors the stores to Supabase when configured: `load_or_seed()` at startup (empty tables get the seed), and routers call `db.save_*()` after each change. `app/auth.py` checks the Supabase access token (`/auth/v1/user`, cached 60 s) and reads the role from `profiles`; `/me` returns it. `app/mock_data.py` holds every store in memory (reset on restart unless Supabase is on): 60 seeded patients (about a third in the demo district), 3 drafted suggestions per district, a week of counter screenings, 11 cases at every step, van slots and the ABHA demo records. `mock_risk()` stands in for the XGBoost model in `ml/dropout` (rule points ranked like SHAP reasons). Tests use `TestClient(app)` and import `app.main` (pytest `pythonpath = ["."]`).

`apps/web` uses the App Router: `/` (portal chooser), `/login`, `app/(counter)/counter` and `app/(asha)/asha` (each wrapped in `components/auth-gate.tsx`, which sends signed-out users to `/login`; `lib/supabase.ts` only signs in and adds the token in `lib/api.ts`); `/screen` and `/dashboard` redirect (`next.config.ts`). Pages are client components built from `components/` (`app-header`, `logo`, `journey-card`, `panel`, `pill`, `drawer`, `counter/*`, `asha/*`). Labels and Title Case live in `lib/labels.ts`. Theme: teal tokens in `app/globals.css`, dark mode via a `dark` class set before paint in `app/layout.tsx`, and the lab watermark in `public/watermark-*.svg`. The UI uses shadcn/ui (`base-nova` on `@base-ui/react`) and Tailwind v4 through `@tailwindcss/turbopack`. Under WSL the dev server sometimes misses CSS edits: stop it, `rm -rf apps/web/.next`, restart.

## Glossary

| Term | Meaning → code |
| --- | --- |
| TBC² | The project name ("TB Care Coordinator"); logo in `components/logo.tsx` |
| Counter | A pharmacy or local practitioner who screens and forwards → `app/(counter)/counter` |
| ASHA | Accredited Social Health Activist, a community health worker → `app/(asha)/asha` |
| Ni-kshay | India's national TB patient system. We never connect to it |
| Ni-kshay Poshan Yojana | Government nutrition support, ₹1,000/month during treatment → `gets_nutrition_support` |
| ABHA | Ayushman Bharat Health Account, a 14-digit health ID. Simulated lookup only → `/abha/lookup` |
| IsoScreen | Urine strip test for isoniazid, a spot check on self-reported doses → `isoscreen_tests` |
| NAAT | Molecular sputum test (Truenat / CBNAAT) that confirms TB and rifampicin resistance (RR) → `NaatResult` |
| Mobile X-ray van | Weekly van visits with X-ray → `/van-slots` |
| CXR | Chest X-ray → `xray_score`, `ml/cxr` |
| Grad-CAM | Heatmap of where the X-ray model looked (planned) |
| Dropout / loss to follow-up | A patient stopping treatment → `/risk/weekly`, `ml/dropout` |
| SHAP | Per-feature explanation of the dropout score → `RiskEntry.reasons` |
| Drug-sensitive / drug-resistant | TB regimen types → `Patient.regimen` |
| TBscreen / Coswara | Clinic TB and non-TB coughs (`PID_*`) / crowdsourced healthy coughs (`COSWARA_*`) → `data/raw/Cough_Audio` |
| JU-TB | 55k TB/Normal chest X-ray set → `data/raw/CXR` |
