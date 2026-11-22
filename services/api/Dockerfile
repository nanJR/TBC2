# The TBC² API as a Docker image. Deployed on Render (render.yaml at the repo root);
# it listens on $PORT (Render sets it), or 7860 elsewhere (e.g. a Hugging Face Space).
#
# The model files are not in git (CLAUDE.md). They live in a private Hugging Face model
# repo, and scripts/fetch_models.py downloads them when the container starts, using
# MODEL_REPO and a read-only HF_TOKEN. Other settings: SUPABASE_URL,
# SUPABASE_SECRET_KEY, REQUIRE_LOGIN and FRONTEND_ORIGIN.

FROM python:3.12-slim

# Run as a normal user (uid 1000), not root.
RUN useradd -m -u 1000 user && pip install --no-cache-dir uv==0.13.5
WORKDIR /home/user/app

# Install the exact locked packages first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && uv pip install --python .venv huggingface_hub==2.4.0

COPY app ./app
COPY scripts/fetch_models.py ./scripts/fetch_models.py
RUN mkdir -p models && chown -R user /home/user/app
USER user

ENV PATH="/home/user/app/.venv/bin:$PATH" \
    MODEL_DIR=/home/user/app/models \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["sh", "-c", "python scripts/fetch_models.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
