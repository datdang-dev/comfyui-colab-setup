"""Main entry point — full setup flow.

Called from Colab notebook with parameters.
ComfyUI is cloned by the notebook before calling this.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config
from .ui import Color, run_cmd


def parse_args():
    """Parse command-line arguments (for subprocess mode)."""
    parser = argparse.ArgumentParser(description="ComfyUI Colab Setup")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--repo-id", default=config.DEFAULT_REPO_ID)
    parser.add_argument("--repo-type", default=config.DEFAULT_REPO_TYPE)
    parser.add_argument("--max-parallel", type=int, default=config.MAX_DOWNLOAD_PARALLEL)
    parser.add_argument("--workspace", default=config.WORKSPACE)
    parser.add_argument("--custom-nodes", nargs="*", help="Additional node URLs to install")
    parser.add_argument("--skip-nodes", action="store_true", help="Skip custom node installation")
    parser.add_argument("--skip-select", action="store_true", help="Skip interactive selection (use existing download_list.json)")
    parser.add_argument("--skip-download", action="store_true", help="Skip model download")
    return parser.parse_args()


def run(hf_token=None, repo_id=None, repo_type=None, max_parallel=None, workspace=None):
    """Run full setup from notebook (interactive mode)."""
    args = parse_args.__wrapped__() if hasattr(parse_args, '__wrapped__') else argparse.Namespace(
        hf_token=hf_token or "",
        repo_id=repo_id or config.DEFAULT_REPO_ID,
        repo_type=repo_type or config.DEFAULT_REPO_TYPE,
        max_parallel=max_parallel or config.MAX_DOWNLOAD_PARALLEL,
        workspace=workspace or config.WORKSPACE,
        custom_nodes=None,
        skip_nodes=False,
        skip_select=False,
        skip_download=False,
    )
    _run_with_args(args)


def run_from_notebook(hf_token, repo_id, repo_type, max_parallel, workspace):
    """Called directly from notebook cell."""
    args = argparse.Namespace(
        hf_token=hf_token or "",
        repo_id=repo_id or config.DEFAULT_REPO_ID,
        repo_type=repo_type or config.DEFAULT_REPO_TYPE,
        max_parallel=max_parallel or config.MAX_DOWNLOAD_PARALLEL,
        workspace=workspace or config.WORKSPACE,
        custom_nodes=None,
        skip_nodes=False,
        skip_select=False,
        skip_download=False,
    )
    _run_with_args(args)


def _run_with_args(args):
    """Core setup flow with parsed args."""
    # Resolve HF token
    auth_token = args.hf_token if args.hf_token and args.hf_token.strip() else None
    if not auth_token:
        env_token = os.environ.get("HF_TOKEN", "")
        auth_token = env_token if env_token.strip() else None

    if not auth_token:
        print(f"  {Color.WARNING}⚠️  No HF_TOKEN — private repos will not be accessible{Color.ENDC}")

    workspace = Path(args.workspace)
    comfy_dir = workspace / "ComfyUI"
    base_dir = str(workspace / "ComfyUI" / "models")

    # ── Step 1: Clone ComfyUI (if not already cloned) ──
    if not comfy_dir.exists():
        print(f"\n{'='*55}")
        print(f"  📥 CLONE COMFYUI")
        print(f"{'='*55}")
        run_cmd(f"git clone --depth=1 {config.COMFYUI_REPO}", cwd=workspace)
        req = comfy_dir / "requirements.txt"
        if req.exists():
            run_cmd(f"pip install -q -r {req}")
        (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
        print(f"  {Color.OKGREEN}✅ ComfyUI core ready{Color.ENDC}")
    else:
        print(f"  {Color.OKBLUE}🔄 ComfyUI already cloned{Color.ENDC}")

    # ── Step 2: Install Nodes (background) + Select Models (interactive) ──
    if not args.skip_nodes:
        print(f"\n{'='*55}")
        print(f"  🧩 INSTALL CUSTOM NODES (background)")
        print(f"{'='*55}")
        from . import nodes
        script = nodes.generate_install_script(comfy_dir, extra_nodes=args.custom_nodes)
        script_path = "/tmp/_install_nodes.py"
        with open(script_path, "w") as f:
            f.write(script)

        nodes_proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(f"  PID: {nodes_proc.pid} — nodes installing in background\n")

    # ── Step 3: Select Models ──
    if not args.skip_select:
        print(f"\n{'='*55}")
        print(f"  📥 SELECT MODELS")
        print(f"{'='*55}")
        from .select import run_selection
        run_selection(
            repo_id=args.repo_id,
            repo_type=args.repo_type,
            base_dir=base_dir,
            auth_token=auth_token,
        )

    # ── Step 4: Download Models ──
    if not args.skip_download:
        print(f"\n{'='*55}")
        print(f"  📦 DOWNLOAD MODELS")
        print(f"{'='*55}")
        from .models import load_and_download
        load_and_download(auth_token=auth_token, max_parallel=args.max_parallel)

    # ── Step 5: Wait for nodes (if started) ──
    if not args.skip_nodes:
        print(f"\n  ⏳ Waiting for node installation...")
        while True:
            result = subprocess.run(f"ps -p {nodes_proc.pid}", shell=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                break
            time.sleep(2)
        print(f"  {Color.OKGREEN}✅ Nodes installed{Color.ENDC}")

    print(f"\n  {Color.OKGREEN}{'='*55}{Color.ENDC}")
    print(f"  {Color.OKGREEN}✅ Setup complete!{Color.ENDC}")
    print(f"  {Color.OKGREEN}{'='*55}{Color.ENDC}\n")


if __name__ == "__main__":
    args = parse_args()
    _run_with_args(args)
