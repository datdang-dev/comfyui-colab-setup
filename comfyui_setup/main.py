"""Main entry point — full setup flow.

Called from Colab notebook with parameters, or from install.py CLI.
Orchestrates: clone → nodes (background) → select → download → wait.
"""

import argparse
import os
import time
from pathlib import Path

from . import config
from .core import clone_comfyui, load_prebuilt
from .models import load_and_download
from .nodes import start_background_install
from .select import run_selection
from .ui import Color, get_logger, print_header, setup_logging


def parse_args():
    """Parse command-line arguments (for subprocess mode)."""
    parser = argparse.ArgumentParser(description="ComfyUI Colab Setup")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--repo-id", default=config.DEFAULT_REPO_ID)
    parser.add_argument("--repo-type", default=config.DEFAULT_REPO_TYPE)
    parser.add_argument("--max-parallel", type=int, default=config.MAX_DOWNLOAD_PARALLEL)
    parser.add_argument("--workspace", default=str(config.WORKSPACE))
    parser.add_argument("--custom-nodes", nargs="*", help="Additional node URLs to install")
    parser.add_argument("--skip-nodes", action="store_true", help="Skip custom node installation")
    parser.add_argument("--skip-select", action="store_true", help="Skip interactive selection")
    parser.add_argument("--skip-download", action="store_true", help="Skip model download")
    parser.add_argument("--use-prebuilt", action="store_true", help="Load pre-built env from HF")
    parser.add_argument("--env-repo", default=config.DEFAULT_ENV_REPO, help="HF dataset with pre-built env")
    return parser.parse_args()


def run(hf_token=None, repo_id=None, repo_type=None, max_parallel=None, workspace=None,
        use_prebuilt=False, env_repo=None, skip_nodes=False, skip_select=False, skip_download=False):
    """Run full setup programmatically (called from notebook cell)."""
    _run(
        hf_token=hf_token or "",
        repo_id=repo_id or config.DEFAULT_REPO_ID,
        repo_type=repo_type or config.DEFAULT_REPO_TYPE,
        max_parallel=max_parallel or config.MAX_DOWNLOAD_PARALLEL,
        workspace=workspace or str(config.WORKSPACE),
        custom_nodes=None,
        use_prebuilt=use_prebuilt,
        env_repo=env_repo or config.DEFAULT_ENV_REPO,
        skip_nodes=skip_nodes,
        skip_select=skip_select,
        skip_download=skip_download,
    )


def run_from_notebook(hf_token, repo_id, repo_type, max_parallel, workspace):
    """Legacy entry point for backward compatibility."""
    run(hf_token=hf_token, repo_id=repo_id, repo_type=repo_type,
        max_parallel=max_parallel, workspace=workspace)


def _run(hf_token, repo_id, repo_type, max_parallel, workspace,
         custom_nodes=None, use_prebuilt=False, env_repo=None,
         skip_nodes=False, skip_select=False, skip_download=False):
    """Core setup flow."""
    log = get_logger()
    start_time = time.time()

    # Resolve HF token
    auth_token = hf_token.strip() if hf_token and hf_token.strip() else None
    if not auth_token:
        env_token = os.environ.get("HF_TOKEN", "").strip()
        auth_token = env_token or None

    if not auth_token:
        log.warning("No HF_TOKEN — private repos will not be accessible")

    ws = Path(workspace)
    base_dir = str(ws / "ComfyUI" / "models")

    # ── Step 1: Clone ComfyUI or load prebuilt ──
    print_header("STEP 1: SETUP COMFYUI")
    if use_prebuilt:
        comfy_dir = load_prebuilt(ws, auth_token, env_repo)
    else:
        comfy_dir = clone_comfyui(ws)

    # ── Step 2: Install nodes in background ──
    nodes_proc = None
    if not skip_nodes:
        print_header("STEP 2: INSTALL CUSTOM NODES (background)")
        nodes_proc = start_background_install(comfy_dir)
        log.info("  (You can select models while nodes install)")
        log.info("")

    # ── Step 3: Select models ──
    if not skip_select:
        print_header("STEP 3: SELECT MODELS")
        run_selection(repo_id=repo_id, repo_type=repo_type, base_dir=base_dir, auth_token=auth_token)

    # ── Step 4: Download models ──
    if not skip_download:
        print_header("STEP 4: DOWNLOAD MODELS")
        load_and_download(auth_token=auth_token, max_parallel=max_parallel)

    # ── Step 5: Wait for background nodes ──
    if nodes_proc:
        print_header("STEP 5: WAITING FOR NODES")
        log.info("Waiting for background node install to finish...")
        try:
            nodes_proc.wait(timeout=600)
        except Exception:
            log.warning("Node install timed out — continuing anyway")

        if nodes_proc.returncode == 0:
            log.info(f"{Color.OKGREEN}Nodes installed successfully.{Color.ENDC}")
        else:
            log.warning(f"Node install exited with code {nodes_proc.returncode}")

    # ── Done ──
    elapsed = time.time() - start_time
    print_header("SETUP COMPLETE")
    log.info(f"{Color.OKGREEN}Done in {elapsed:.0f}s ({elapsed / 60:.1f}min){Color.ENDC}")


if __name__ == "__main__":
    args = parse_args()
    setup_logging(log_file=str(config.LOG_FILE))
    _run(
        hf_token=args.hf_token,
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        max_parallel=args.max_parallel,
        workspace=args.workspace,
        custom_nodes=args.custom_nodes,
        use_prebuilt=args.use_prebuilt,
        env_repo=args.env_repo,
        skip_nodes=args.skip_nodes,
        skip_select=args.skip_select,
        skip_download=args.skip_download,
    )
