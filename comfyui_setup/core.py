"""ComfyUI core installation — clone repo, install deps, start background node install."""

import os
import subprocess
import sys
from pathlib import Path

from . import config
from .ui import Color, run_cmd


def clone_comfyui(workspace=None):
    """Clone or update ComfyUI core repository."""
    ws = Path(workspace or config.WORKSPACE)
    comfy_dir = ws / "ComfyUI"

    if not comfy_dir.exists():
        print(f"\n  {Color.OKBLUE}📥 Cloning ComfyUI...{Color.ENDC}")
        run_cmd(f"git clone --depth=1 {config.COMFYUI_REPO}", cwd=ws)
    else:
        print(f"\n  {Color.OKBLUE}🔄 Updating ComfyUI...{Color.ENDC}")
        run_cmd("git pull", cwd=comfy_dir)

    # Install core requirements
    req = comfy_dir / "requirements.txt"
    if req.exists():
        print(f"  {Color.OKBLUE}📦 Installing core deps...{Color.ENDC}")
        run_cmd(f"pip install -q -r {req}")

    nodes_dir = comfy_dir / "custom_nodes"
    nodes_dir.mkdir(exist_ok=True)
    print(f"  {Color.OKGREEN}✅ ComfyUI core ready{Color.ENDC}")

    return comfy_dir


def start_background_nodes(comfy_dir):
    """Start custom node installation in background subprocess. Returns PID."""
    from . import nodes

    script_content = nodes.generate_install_script(comfy_dir)
    script_path = "/tmp/_install_nodes.py"

    with open(script_path, "w") as f:
        f.write(script_content)

    print(f"  {Color.OKBLUE}🧩 Starting node install in background...{Color.ENDC}")
    print(f"     (You can select models while nodes install)\n")

    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    return proc.pid
