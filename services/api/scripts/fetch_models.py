"""Download the model files from a private Hugging Face repo into MODEL_DIR.

Used by the Docker image at start-up. Needs MODEL_REPO (e.g. "user/tbc2-models") and a
read-only HF_TOKEN. If MODEL_REPO isn't set, nothing is downloaded and the API runs
without models (scores stay empty), which is also what happens on a machine without them.
"""

import os

repo = os.environ.get("MODEL_REPO")
if repo:
    from huggingface_hub import snapshot_download

    target = os.environ.get("MODEL_DIR", "models")
    snapshot_download(repo_id=repo, local_dir=target, token=os.environ.get("HF_TOKEN"))
    print(f"Models downloaded from {repo} into {target}")
else:
    print("MODEL_REPO not set: starting without models")
