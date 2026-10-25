# TBC² — AI-powered TB care coordinator

TBC² helps community health workers screen people for tuberculosis and helps
district teams spot patients who are likely to stop their treatment, so someone
can follow up in time.

> **Prototype for learning only. Not for clinical use.**
> It uses public datasets and synthetic (fake) patients only. No real patient
> data, and no connection to Ni-kshay or any ASHA system.

A project by **The MedMinds**.

## How it works

1. The **ASHA-style phone app** records a short cough and can upload a chest X-ray.
2. The **back end** runs two screening models (cough and X-ray) and combines them
   into one TB risk score, with a heatmap of where the X-ray model looked.
3. For patients on treatment, a **dropout-risk model** (XGBoost + SHAP) gives a
   weekly risk score and the main reasons behind it.
4. An **AI agent** drafts a next step for each high-risk patient (SMS, home visit,
   nutrition support).
5. A person on the **district dashboard** clicks Approve or Reject. Nothing is sent
   without that click.

## Repo layout

| Folder | What lives there | Stack |
| --- | --- | --- |
| [`apps/web`](apps/web) | ASHA phone app (PWA) + district dashboard | Next.js, React, TypeScript, Tailwind, shadcn/ui |
| [`services/api`](services/api) | REST API, database, model serving | FastAPI, Pydantic, Postgres (Supabase) |
| [`agent`](agent) | AI agent, its tools and test cases | LangGraph |
| [`ml/cough`](ml) | Cough-sound TB model | PyTorch, librosa |
| [`ml/cxr`](ml) | Chest X-ray TB model + Grad-CAM | PyTorch, timm |
| [`ml/dropout`](ml) | Treatment dropout-risk model | XGBoost, SHAP |
| [`ml/export`](ml) | Convert models to ONNX, upload to Hugging Face | ONNX Runtime |
| [`data`](data) | Dataset download notes + synthetic patient generator | Python |
| [`sim`](sim) | District simulation (with vs without TBC²) | Mesa |
| [`docs`](docs) | Architecture, report drafts | |

## Run it locally

You need **Node.js 20+**, **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**.

**Back end** (http://localhost:8000, API docs at http://localhost:8000/docs):

```bash
cd services/api
uv sync
uv run fastapi dev app/main.py
```

**Front end** (http://localhost:3000), in a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

The home page calls the back end's `/health` endpoint and shows whether it is up.

**Or start both at once** (Linux, macOS or WSL), with logs tagged `[api]` and `[web]`:

```bash
./scripts/dev.sh
```

If another project already uses port 8000 or 3000, pick others:
`API_PORT=8100 WEB_PORT=3100 ./scripts/dev.sh`

### tmux workspace (WSL)

`./scripts/tmux-dev.sh` opens a tmux session called `TBC2`: Claude Code on the
left, the dev servers top-right, lazygit bottom-right. Run it again to reattach.
It needs `tmux`, `lazygit`, `claude`, `uv` and Node.js installed inside WSL.
Clone the repo inside WSL (for example `~/code/TBC2`), not under `/mnt/c`:
packages installed by Windows don't run on Linux, and `/mnt/c` is slow.

## Team rules

- **Never commit secrets, datasets or model weights.** `.gitignore` blocks the
  common file types, but check `git status` before every commit.
- Keys go in a local `.env` file. Copy `.env.example` and fill it in.
- Work on a branch, open a pull request, and ask a teammate to review it.
- Keep commits small, with a message that says what changed.

## Data sources

See [`data/README.md`](data/README.md) for every dataset, where it comes from and its licence.
