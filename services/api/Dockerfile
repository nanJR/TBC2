# The TBC² API as a Docker image, for a Hugging Face Space (Docker SDK, port 7860).
#
# The model files are not in git (CLAUDE.md). They live in a private Hugging Face model
# repo, and scripts/fetch_models.py downloads them when the container starts, using the
# Space secrets MODEL_REPO and HF_TOKEN. Other secrets: SUPABASE_URL,
# SUPABASE_SECRET_KEY and FRONTEND_ORIGIN (see deploy/README.md).

FROM python:3.12-slim

# Spaces run the container as user 1000.
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
CMD ["sh", "-c", "python scripts/fetch_models.py && uvicorn app.main:app --host 0.0.0.0 --port 7860"]
