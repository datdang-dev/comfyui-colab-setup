#!/usr/bin/env python3
"""
ComfyUI Environment Setup Script
=================================
Run this script ONCE to build and upload pre-built environment to HuggingFace.

Usage:
    python setup_env.py --hf-token=YOUR_TOKEN

Or set HF_TOKEN environment variable:
    export HF_TOKEN=***    python setup_env.py
"""

import argparse
import os
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

# ── Config ──
SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
ENV_REPO = "datsss/comfyui-env"
WORKSPACE = Path("/content")


class Color:
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(msg):
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*55}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}  {msg}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*55}{Color.END}\n")


def print_ok(msg):
    print(f"{Color.GREEN}✅ {msg}{Color.END}")


def print_err(msg):
    print(f"{Color.RED}❌ {msg}{Color.END}")


def run(cmd, cwd=None, quiet=False):
    """Run command and return success/failure."""
    try:
        subprocess.run(
            cmd, shell=True, check=True, cwd=cwd,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
        return True
    except subprocess.CalledProcessError:
        return False


# ── Step 1: Clone repos ──
def clone_repos():
    print_header("STEP 1: Clone Repos")

    # Setup repo
    setup_dir = WORKSPACE / "comfyui-colab-setup"
    if not setup_dir.exists():
        print("Cloning setup repo...")
        run(f"git clone --depth=1 {SETUP_REPO} {setup_dir}")
    else:
        print("Setup repo exists, pulling...")
        run("git pull", cwd=setup_dir)

    # ComfyUI
    comfy_dir = WORKSPACE / "ComfyUI"
    if not comfy_dir.exists():
        print("\nCloning ComfyUI...")
        run(f"git clone --depth=1 {COMFYUI_REPO} {WORKSPACE}/ComfyUI")
    else:
        print("\nComfyUI exists, pulling...")
        run("git pull", cwd=comfy_dir)

    return setup_dir, comfy_dir


# ── Step 2: Install dependencies ──
def install_deps(setup_dir):
    print_header("STEP 2: Install Dependencies")

    # Core deps
    print("Installing core dependencies...")
    run(f"pip install -q -r {setup_dir / 'requirements.txt'}")

    # Custom nodes
    import yaml
    config_file = setup_dir / "config.yaml"
    if not config_file.exists():
        print_err("config.yaml not found!")
        return

    with open(config_file) as f:
        config = yaml.safe_load(f)

    nodes = config.get("nodes", [])
    comfy_dir = WORKSPACE / "ComfyUI"
    nodes_dir = comfy_dir / "custom_nodes"
    nodes_dir.mkdir(exist_ok=True)

    print(f"\nInstalling {len(nodes)} custom nodes...")
    ok = 0
    fail = 0
    for i, node in enumerate(nodes, 1):
        name = node["name"]
        url = node["url"]
        dest = nodes_dir / name

        if not dest.exists():
            print(f"  [{i:2d}/{len(nodes)}] {name}...", end=" ", flush=True)
            if run(f"git clone --depth=1 {url}", cwd=nodes_dir, quiet=True):
                print("✓")
                ok += 1
            else:
                print("✗")
                fail += 1
        else:
            print(f"  [{i:2d}/{len(nodes)}] {name} exists")
            ok += 1

    # Node deps
    print(f"\nInstalling node dependencies...")
    pip_args = []
    for p in nodes_dir.iterdir():
        if p.is_dir():
            req = p / "requirements.txt"
            if req.exists():
                pip_args.append(str(req))

    for i in range(0, len(pip_args), 5):
        batch = pip_args[i:i+5]
        reqs = " ".join([f"-r {r}" for r in batch])
        run(f"pip install -q {reqs}", quiet=True)

    print_ok(f"Dependencies installed: {ok}/{len(nodes)} nodes")


# ── Step 3: Package environment (parallel) ──
def package_env():
    print_header("STEP 3: Package Environment")

    comfy_dir = WORKSPACE / "ComfyUI"
    nodes_dir = comfy_dir / "custom_nodes"
    site_packages = Path(subprocess.check_output(
        "python -c 'import site; print(site.getsitepackages()[0])'",
        shell=True, text=True).strip())

    results = {}

    def pack_nodes():
        print("[1/2] Packaging custom_nodes...")
        nodes_tar = WORKSPACE / "custom_nodes.tar.gz"
        with tarfile.open(nodes_tar, "w:gz") as tar:
            dirs = [d for d in nodes_dir.iterdir() if d.is_dir()]
            for i, node_dir in enumerate(dirs, 1):
                print(f"  [{i}/{len(dirs)}] {node_dir.name}", flush=True)
                tar.add(node_dir, arcname=f"ComfyUI/custom_nodes/{node_dir.name}")
        size = nodes_tar.stat().st_size / (1024*1024)
        print(f"  ✅ custom_nodes.tar.gz: {size:.0f}MB")
        results["nodes"] = nodes_tar

    def pack_env():
        print("[2/2] Packaging Python environment...")
        env_tar = WORKSPACE / "comfyui-env.tar.gz"
        with tarfile.open(env_tar, "w:gz") as tar:
            print(f"  Adding site-packages...", flush=True)
            tar.add(site_packages, arcname="site-packages")
            items = [i for i in comfy_dir.iterdir() if i.name != "custom_nodes"]
            for i, item in enumerate(items, 1):
                print(f"  [{i}/{len(items)}] {item.name}", flush=True)
                tar.add(item, arcname=f"ComfyUI/{item.name}")
        size = env_tar.stat().st_size / (1024*1024)
        print(f"  ✅ comfyui-env.tar.gz: {size:.0f}MB")
        results["env"] = env_tar

    # Run both in parallel
    t1 = threading.Thread(target=pack_nodes)
    t2 = threading.Thread(target=pack_env)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print_ok("Packaging complete!")
    return results["nodes"], results["env"]


# ── Step 4: Upload to HF ──
def upload_hf(nodes_tar, env_tar, hf_token):
    print_header("STEP 4: Upload to HuggingFace")

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=ENV_REPO, repo_type="dataset", token=hf_token, exist_ok=True)

    # Upload custom_nodes
    print(f"Uploading custom_nodes.tar.gz ({nodes_tar.stat().st_size/(1024*1024):.0f}MB)...")
    api.upload_file(
        path_or_fileobj=str(nodes_tar),
        path_in_repo="custom_nodes.tar.gz",
        repo_id=ENV_REPO,
        repo_type="dataset",
        token=hf_token,
    )

    # Upload env
    print(f"Uploading comfyui-env.tar.gz ({env_tar.stat().st_size/(1024*1024):.0f}MB)...")
    api.upload_file(
        path_or_fileobj=str(env_tar),
        path_in_repo="comfyui-env.tar.gz",
        repo_id=ENV_REPO,
        repo_type="dataset",
        token=hf_token,
    )

    print_ok(f"Upload complete!")
    print(f"\n  Dataset: https://huggingface.co/datasets/{ENV_REPO}")


# ── Main ──
def main():
    parser = argparse.ArgumentParser(description="ComfyUI Environment Setup")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--skip-install", action="store_true", help="Skip installation step")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload step")
    args = parser.parse_args()

    # Resolve token
    hf_token = args.hf_token.strip() or None
    if not hf_token and not args.skip_upload:
        import getpass
        hf_token = getpass.getpass("HF Token: ")

    start = time.time()

    # Run steps
    setup_dir, comfy_dir = clone_repos()

    if not args.skip_install:
        install_deps(setup_dir)

    nodes_tar, env_tar = package_env()

    if not args.skip_upload and hf_token:
        upload_hf(nodes_tar, env_tar, hf_token)

    elapsed = time.time() - start
    print_ok(f"Done in {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
