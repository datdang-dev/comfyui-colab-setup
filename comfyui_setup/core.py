"""ComfyUI core installation — clone repo, install deps."""

import subprocess
from pathlib import Path

from . import config
from .ui import Color, get_logger, print_header, run_cmd


def clone_comfyui(workspace=None):
    """Clone or update ComfyUI core repository.

    Returns the comfy_dir Path. Uses config.yaml for the repo URL and version.
    """
    log = get_logger()
    ws = Path(workspace or config.WORKSPACE)
    comfy_dir = ws / "ComfyUI"
    comfyui_repo = config.get_comfyui_repo()
    comfy_version = config.get_comfyui_version()

    # If comfy_version is latest_release, we don't pass it to depth clone directly
    # since it needs tags mapping, or we clone normally.
    if comfy_version == "latest_release":
        comfy_version = ""

    if not comfy_dir.exists():
        log.info(f"Cloning ComfyUI from {comfyui_repo}...")
        if comfy_version:
            log.info(f"Checking out ComfyUI version/branch/commit '{comfy_version}'...")
            r = subprocess.run(f"git clone --depth=1 --branch {comfy_version} {comfyui_repo} {comfy_dir}", shell=True)
            if r.returncode != 0:
                log.info(f"Shallow clone failed. Cloning full repo and checking out '{comfy_version}'...")
                run_cmd(f"git clone {comfyui_repo} {comfy_dir}")
                run_cmd(f"git checkout {comfy_version}", cwd=str(comfy_dir))
        else:
            run_cmd(f"git clone --depth=1 {comfyui_repo} {comfy_dir}")
        # Install core requirements
        req = comfy_dir / "requirements.txt"
        if req.exists():
            log.info("Installing ComfyUI core dependencies...")
            run_cmd(f"pip install -q -r {req}")
        (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
        log.info(f"{Color.OKGREEN}ComfyUI core ready{Color.ENDC}")
    else:
        if comfy_version:
            log.info(f"ComfyUI exists, checking out '{comfy_version}'...")
            run_cmd("git fetch --all", cwd=str(comfy_dir), quiet=True)
            run_cmd(f"git checkout {comfy_version}", cwd=str(comfy_dir))
        else:
            log.info(f"{Color.OKBLUE}ComfyUI already cloned, pulling updates...{Color.ENDC}")
            run_cmd("git pull", cwd=str(comfy_dir), quiet=True)

    return comfy_dir


def load_prebuilt(workspace=None, auth_token=None, env_repo=None):
    """Download, clone, and extract pre-built environment from HuggingFace.

    Expects three files on the HF dataset:
      - metadata.json       → contains target ComfyUI commit hash
      - comfyui-env.tar.gz  → contains site-packages/ only
      - custom_nodes.tar.gz → contains custom_nodes/

    Returns comfy_dir.
    """
    log = get_logger()
    import json
    from huggingface_hub import hf_hub_download

    ws = Path(workspace or config.WORKSPACE)
    env_repo = env_repo or config.DEFAULT_ENV_REPO
    comfy_dir = ws / "ComfyUI"

    log.info(f"Loading pre-built environment from {env_repo}...")

    # 1. Download metadata.json
    log.info("  Downloading metadata.json...")
    comfy_commit = ""
    try:
        meta_file = hf_hub_download(
            repo_id=env_repo,
            filename="metadata.json",
            repo_type="dataset",
            token=auth_token,
            local_dir=str(ws),
        )
        with open(meta_file, "r") as f:
            meta = json.load(f)
            comfy_commit = meta.get("comfyui_commit", "")
            log.info(f"  Prebuilt environment maps to ComfyUI commit: {comfy_commit}")
    except Exception as e:
        log.warning(f"  Failed to retrieve or read metadata.json: {e}")

    # 2. Download comfyui-env.tar.gz (site-packages only)
    log.info("  Downloading comfyui-env.tar.gz...")
    env_archive = hf_hub_download(
        repo_id=env_repo,
        filename="comfyui-env.tar.gz",
        repo_type="dataset",
        token=auth_token,
    )
    log.info(f"  Extracting site-packages into {ws}...")
    # Use -C to extract to parent of site-packages (workspace)
    subprocess.run(f"tar -xzf {env_archive} -C {ws}", shell=True, check=True)

    # 3. Restore site-packages into system Python via .pth file (instantaneous)
    site_pkg = config.get_site_packages()
    sp_dir = ws / "site-packages"
    if not sp_dir.exists():
        sp_dir = ws / "dist-packages"
        
    if sp_dir.exists():
        log.info(f"  Registering site-packages dynamically via .pth...")
        pth_file = site_pkg / "comfyui_env.pth"
        pth_file.write_text(f"{sp_dir}\n", encoding="utf-8")
    else:
        log.warning("  No site-packages or dist-packages directory found to link!")
    log.info(f"  {Color.OKGREEN}Python environment linked instantly{Color.ENDC}")

    # 4. Clone ComfyUI core dynamically if missing
    comfyui_repo = config.get_comfyui_repo()
    if not comfy_dir.exists():
        log.info(f"  Cloning ComfyUI core from {comfyui_repo}...")
        run_cmd(f"git clone {comfyui_repo} {comfy_dir}")

    # 5. Checkout matching version to align with prebuilt environment dependencies
    if comfy_commit:
        log.info(f"  Checking out commit {comfy_commit}...")
        subprocess.run(f"git checkout -q {comfy_commit}", shell=True, cwd=str(comfy_dir), check=True)

    # 6. Download + extract custom_nodes.tar.gz into ComfyUI
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

