"""ComfyUI core installation — clone repo, install deps."""

import subprocess
from pathlib import Path

from . import config
from .ui import Color, get_logger, print_header, run_cmd


def clone_comfyui(workspace=None):
    """Clone or update ComfyUI core repository.

    Returns the comfy_dir Path. Uses config.yaml for the repo URL.
    """
    log = get_logger()
    ws = Path(workspace or config.WORKSPACE)
    comfy_dir = ws / "ComfyUI"
    comfyui_repo = config.get_comfyui_repo()

    if not comfy_dir.exists():
        log.info(f"Cloning ComfyUI from {comfyui_repo}...")
        run_cmd(f"git clone --depth=1 {comfyui_repo}", cwd=str(ws))
        # Install core requirements
        req = comfy_dir / "requirements.txt"
        if req.exists():
            log.info("Installing ComfyUI core dependencies...")
            run_cmd(f"pip install -q -r {req}")
        (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
        log.info(f"{Color.OKGREEN}ComfyUI core ready{Color.ENDC}")
    else:
        log.info(f"{Color.OKBLUE}ComfyUI already cloned, pulling updates...{Color.ENDC}")
        run_cmd("git pull", cwd=str(comfy_dir), quiet=True)

    return comfy_dir


def load_prebuilt(workspace=None, auth_token=None, env_repo=None):
    """Download and extract pre-built environment from HuggingFace.

    Expects two archives on the HF dataset:
      - comfyui-env.tar.gz  → contains site-packages/ + ComfyUI/ (core)
      - custom_nodes.tar.gz → contains custom_nodes/

    Returns comfy_dir.
    """
    log = get_logger()
    from huggingface_hub import hf_hub_download

    ws = Path(workspace or config.WORKSPACE)
    env_repo = env_repo or config.DEFAULT_ENV_REPO
    comfy_dir = ws / "ComfyUI"

    log.info(f"Loading pre-built environment from {env_repo}...")

    # Download + extract comfyui-env.tar.gz (site-packages + ComfyUI core)
    log.info("  Downloading comfyui-env.tar.gz...")
    env_archive = hf_hub_download(
        repo_id=env_repo,
        filename="comfyui-env.tar.gz",
        repo_type="dataset",
        token=auth_token,
    )
    log.info(f"  Extracting comfyui-env.tar.gz into {ws}...")
    subprocess.run(f"tar -xzf {env_archive} -C {ws}", shell=True, check=True)

    # Restore site-packages into system Python
    site_pkg = config.get_site_packages()
    sp_dir = ws / "site-packages"
    if sp_dir.exists():
        log.info(f"  Restoring site-packages to {site_pkg}...")
        subprocess.run(
            f"cp -rn {sp_dir}/* {site_pkg}/ 2>/dev/null; "
            f"cp -rn {sp_dir}/.[!.]* {site_pkg}/ 2>/dev/null",
            shell=True,
        )
    log.info(f"  {Color.OKGREEN}Python environment ready{Color.ENDC}")

    # Download + extract custom_nodes.tar.gz
    log.info("  Downloading custom_nodes.tar.gz...")
    nodes_archive = hf_hub_download(
        repo_id=env_repo,
        filename="custom_nodes.tar.gz",
        repo_type="dataset",
        token=auth_token,
    )
    log.info(f"  Extracting custom_nodes into {comfy_dir}...")
    subprocess.run(f"tar -xzf {nodes_archive} -C {comfy_dir}", shell=True, check=True)
    log.info(f"  {Color.OKGREEN}Custom nodes ready{Color.ENDC}")

    return comfy_dir

