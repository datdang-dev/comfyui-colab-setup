"""Main entry point — full setup flow."""

from . import config
from .ui import Color
from .core import clone_comfyui, start_background_nodes
from .select import run_selection
from .models import load_and_download


def run(
    hf_token=None,
    repo_id=None,
    repo_type=None,
    max_parallel=None,
    base_dir=None,
):
    """Run full setup: clone → select → download."""
    # Resolve HF token
    import os
    auth_token = hf_token if hf_token and hf_token.strip() else None
    if not auth_token:
        env_token = os.environ.get("HF_TOKEN", "")
        auth_token = env_token if env_token.strip() else None

    if not auth_token:
        print(f"  {Color.WARNING}⚠️  No HF_TOKEN — private repos will not be accessible{Color.ENDC}")

    base = base_dir or os.path.join(config.WORKSPACE, "ComfyUI", "models")

    # ── Step 1: Clone ComfyUI + start background nodes ──
    comfy_dir = clone_comfyui()
    nodes_pid = start_background_nodes(comfy_dir)

    # ── Step 2: Select models (nodes installing in background) ──
    print(f"\n{'='*55}")
    print(f"  📥 SELECT MODELS")
    print(f"{'='*55}")
    run_selection(
        repo_id=repo_id,
        repo_type=repo_type,
        base_dir=base,
        auth_token=auth_token,
    )

    # ── Step 3: Download models ──
    print(f"\n{'='*55}")
    print(f"  📦 DOWNLOAD MODELS")
    print(f"{'='*55}")
    load_and_download(auth_token=auth_token, max_parallel=max_parallel)

    print(f"\n  {Color.OKGREEN}✅ Setup complete!{Color.ENDC}")
