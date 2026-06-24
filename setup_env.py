#!/usr/bin/env python3
"""
ComfyUI Environment Build Script
=================================
Run ONCE on Colab to build and upload a pre-built environment to HuggingFace.
After upload, the main notebook can load it in ~2 minutes instead of installing from scratch.

Optimizations:
  - pigz (parallel gzip) for 2-4x faster compression on multi-core Colab instances
  - Excludes .git / __pycache__ from tarballs to reduce size
  - Parallel upload of both tarballs
  - Timestamped logging to console + file
  - Reads node list from config.yaml (not hardcoded)

Usage:
    python setup_env.py --hf-token=YOUR_TOKEN
    python setup_env.py --hf-token=YOUR_TOKEN --skip-install
    python setup_env.py --skip-install --skip-upload   # packaging only
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread, Event

# ── Project imports ──
sys.path.insert(0, str(Path(__file__).parent))

from comfyui_setup.config import get_custom_nodes, get_site_packages
from comfyui_setup.nodes import tar_filter
from comfyui_setup.ui import Color, setup_logging, print_header, run_cmd, timer


WORKSPACE = Path("/content")
SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
ENV_REPO = "datsss/comfyui-env"


# ── Compression detection ──
def detect_compression():
    """Detect best available compressor. Returns (method, suffix).

    Priority: pigz > zstd > gzip (fallback).
    pigz is parallel gzip — uses all CPU cores, much faster for large archives.
    """
    if shutil.which("pigz"):
        return "pigz", ".tar.gz"
    if shutil.which("zstd"):
        return "zstd", ".tar.zst"

    # Try to install pigz
    try:
        subprocess.run(
            "apt-get install -y -qq pigz > /dev/null 2>&1", shell=True, check=True, timeout=60
        )
        if shutil.which("pigz"):
            return "pigz", ".tar.gz"
    except Exception:
        pass

    return "gzip", ".tar.gz"


def _progress_reporter(output_path: Path, stop_event: Event, label: str = ""):
    """Background thread that reports output file size every 5s while compression runs."""
    log = setup_logging()
    while not stop_event.is_set():
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            log.info(f"    {label}... {size_mb:.0f}MB so far")
        stop_event.wait(5)
    # Final size
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        log.info(f"    {label}... {size_mb:.0f}MB (done)")


def compress_tar(source_dir, output_path, method, base_dir=None, extra_excludes=None):
    """Create a compressed tarball using the best available compressor.

    Applies tar_filter to exclude .git / __pycache__ directories.
    Shows progress via background file-size reporter.
    """
    log = setup_logging()
    cwd = base_dir or str(source_dir.parent)
    target = source_dir.name if base_dir else str(source_dir)

    if method == "pigz":
        cmd = f"tar -cf - -C {cwd} {target} | pigz -4 > {output_path}"
    elif method == "zstd":
        cmd = f"tar -cf - -C {cwd} {target} | zstd -T4 -3 -o {output_path}"
    else:
        cmd = f"tar -czf {output_path} -C {cwd} {target}"

    log.info(f"  Running: {cmd[:120]}...")

    # Start progress reporter
    stop = Event()
    reporter = Thread(
        target=_progress_reporter, args=(Path(output_path), stop, Path(output_path).name), daemon=True
    )
    reporter.start()
    try:
        subprocess.run(cmd, shell=True, check=True)
    finally:
        stop.set()
        reporter.join(timeout=2)


# ── Step 1: Clone repos ──
def step_clone_repos():
    """Clone the setup repo and ComfyUI core."""
    log = setup_logging()
    print_header("STEP 1: Clone Repos")

    # Setup repo
    setup_dir = WORKSPACE / "comfyui-colab-setup"
    if not setup_dir.exists():
        log.info("Cloning setup repo...")
        run_cmd(f"git clone --depth=1 {SETUP_REPO} {setup_dir}")
    else:
        log.info("Setup repo exists, pulling updates...")
        run_cmd("git pull", cwd=str(setup_dir), quiet=True)

    # ComfyUI
    comfy_dir = WORKSPACE / "ComfyUI"
    if not comfy_dir.exists():
        log.info("Cloning ComfyUI...")
        run_cmd(f"git clone --depth=1 {COMFYUI_REPO} {comfy_dir}")
    else:
        log.info("ComfyUI exists, pulling updates...")
        run_cmd("git pull", cwd=str(comfy_dir), quiet=True)

    return setup_dir, comfy_dir


# ── Step 2: Install dependencies ──
def step_install_deps(setup_dir):
    """Install core deps and all custom nodes from config.yaml."""
    log = setup_logging()
    print_header("STEP 2: Install Dependencies")

    # Core deps from requirements.txt
    req_file = setup_dir / "requirements.txt"
    if req_file.exists():
        log.info("Installing core dependencies...")
        run_cmd(f"pip install -q -r {req_file}")
    else:
        log.warning(f"No requirements.txt found at {req_file}")

    # Custom nodes from config.yaml (via shared config module)
    nodes = get_custom_nodes()
    comfy_dir = WORKSPACE / "ComfyUI"
    nodes_dir = comfy_dir / "custom_nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Installing {len(nodes)} custom nodes...")

    ok = 0
    fail = 0
    for i, node in enumerate(nodes, 1):
        name = node["name"]
        url = node["url"]
        dest = nodes_dir / name

        if dest.exists():
            log.info(f"  [{i:2d}/{len(nodes)}] {name}... exists")
            ok += 1
            continue

        log.info(f"  [{i:2d}/{len(nodes)}] {name}...", end="")
        r = subprocess.run(
            f"git clone --depth=1 {url}",
            shell=True,
            cwd=str(nodes_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if r.returncode == 0:
            ok += 1
            log.info(f"  {Color.OKGREEN}ok{Color.ENDC}")
        else:
            fail += 1
            err = r.stderr.strip().splitlines()[-1] if r.stderr else f"exit {r.returncode}"
            log.info(f"  {Color.FAIL}FAIL: {err}{Color.ENDC}")

    # Node pip deps
    log.info("Installing node dependencies...")
    pip_args = []
    for p in sorted(nodes_dir.iterdir()):
        if p.is_dir():
            req = p / "requirements.txt"
            if req.exists():
                pip_args.append(str(req))

    for i in range(0, len(pip_args), 5):
        batch = pip_args[i : i + 5]
        reqs = " ".join([f"-r {r}" for r in batch])
        batch_num = i // 5 + 1
        total_batches = (len(pip_args) + 4) // 5
        log.info(f"  pip batch {batch_num}/{total_batches}...")
        result = subprocess.run(
            f"pip install -q {reqs}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            for line in (result.stderr or "").strip().splitlines()[-3:]:
                log.warning(f"    {line}")

    log.info(f"{Color.OKGREEN}Done: {ok}/{len(nodes)} nodes installed{Color.ENDC}")


# ── Step 3: Package environment ──
def step_package_env():
    """Package custom_nodes + Python env into compressed tarballs.

    Uses pigz (parallel gzip) for 2-4x faster compression.
    Excludes .git and __pycache__ to reduce archive size.
    """
    log = setup_logging()
    print_header("STEP 3: Package Environment")

    comfy_dir = WORKSPACE / "ComfyUI"
    nodes_dir = comfy_dir / "custom_nodes"
    site_packages = get_site_packages()

    # Detect compression
    method, suffix = detect_compression()
    log.info(f"Compression: {method}{Color.ENDC}")

    nodes_tar = WORKSPACE / f"custom_nodes{suffix}"
    env_tar = WORKSPACE / f"comfyui-env{suffix}"

    # Strip .git and __pycache__ from node dirs before packing
    log.info("Cleaning .git / __pycache__ from custom_nodes to reduce size...")
    for node_dir in nodes_dir.iterdir():
        if node_dir.is_dir():
            for junk_name in [".git", "__pycache__", ".pytest_cache"]:
                junk = node_dir / junk_name
                if junk.exists():
                    shutil.rmtree(junk, ignore_errors=True)

    # Pack in parallel threads
    def pack_nodes():
        log.info("  [1/2] Packaging custom_nodes...")
        with timer() as t:
            cmd = (
                f"tar -cf - --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' "
                f"-C {comfy_dir} custom_nodes | {method} -4 > {nodes_tar}"
            )
            stop = Event()
            reporter = Thread(
                target=_progress_reporter, args=(nodes_tar, stop, "custom_nodes"), daemon=True
            )
            reporter.start()
            try:
                subprocess.run(cmd, shell=True, check=True)
            finally:
                stop.set()
                reporter.join(timeout=2)
        size = nodes_tar.stat().st_size / (1024 * 1024)
        log.info(f"  {Color.OKGREEN}custom_nodes{suffix}: {size:.0f}MB ({t.elapsed:.0f}s){Color.ENDC}")

    def pack_env():
        log.info("  [2/2] Packaging Python environment + ComfyUI core...")
        with timer() as t:
            # Build the env archive: site-packages + ComfyUI (minus custom_nodes)
            # Use a temp directory to stage the structure
            stage_dir = WORKSPACE / "_env_stage"
            stage_dir.mkdir(exist_ok=True)
            (stage_dir / "ComfyUI").mkdir(exist_ok=True)

            # Symlink site-packages into stage
            sp_link = stage_dir / "site-packages"
            if not sp_link.exists():
                os.symlink(str(site_packages), str(sp_link))

            # Symlink ComfyUI core items (skip custom_nodes)
            for item in comfy_dir.iterdir():
                if item.name == "custom_nodes":
                    continue
                link = stage_dir / "ComfyUI" / item.name
                if not link.exists():
                    os.symlink(str(item), str(link))

            # Pack everything from the stage directory
            log.info("    Compressing site-packages + ComfyUI core (this takes a few minutes)...")
            stop = Event()
            reporter = Thread(
                target=_progress_reporter, args=(env_tar, stop, "comfyui-env"), daemon=True
            )
            reporter.start()
            try:
                subprocess.run(
                    f"tar -cf - -C {stage_dir} site-packages ComfyUI | {method} -4 > {env_tar}",
                    shell=True,
                    check=True,
                )
            finally:
                stop.set()
                reporter.join(timeout=2)

            # Clean up symlinks (not the actual files)
            if sp_link.is_symlink():
                sp_link.unlink()
            for link in (stage_dir / "ComfyUI").iterdir():
                if link.is_symlink():
                    link.unlink()
            shutil.rmtree(stage_dir, ignore_errors=True)

        size = env_tar.stat().st_size / (1024 * 1024)
        log.info(f"  {Color.OKGREEN}comfyui-env{suffix}: {size:.0f}MB ({t.elapsed:.0f}s){Color.ENDC}")

    t1 = Thread(target=pack_nodes)
    t2 = Thread(target=pack_env)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    log.info(f"{Color.OKGREEN}Packaging complete.{Color.ENDC}")
    return nodes_tar, env_tar


# ── Step 4: Upload to HuggingFace ──
def step_upload_hf(nodes_tar, env_tar, hf_token):
    log = setup_logging()
    print_header("STEP 4: Upload to HuggingFace")

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=ENV_REPO, repo_type="dataset", token=hf_token, exist_ok=True)

    files_to_upload = [
        (str(nodes_tar), "custom_nodes.tar.gz"),
        (str(env_tar), "comfyui-env.tar.gz"),
    ]

    def upload_one(local_path, repo_path):
        size_mb = Path(local_path).stat().st_size / (1024 * 1024)
        log.info(f"  Uploading {repo_path} ({size_mb:.0f}MB)...")
        with timer() as t:
            api.upload_file(
                path_or_fileobj=local_path,
                path_in_repo=repo_path,
                repo_id=ENV_REPO,
                repo_type="dataset",
                token=hf_token,
            )
        log.info(f"  {Color.OKGREEN}{repo_path} uploaded ({size_mb:.0f}MB in {t.elapsed:.0f}s){Color.ENDC}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload_one, local, remote) for local, remote in files_to_upload]
        for future in futures:
            future.result()

    log.info(f"{Color.OKGREEN}Upload complete.{Color.ENDC}")
    log.info(f"  Dataset: https://huggingface.co/datasets/{ENV_REPO}")


# ── Main ──
def main():
    parser = argparse.ArgumentParser(description="ComfyUI Environment Build Script")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--skip-install", action="store_true", help="Skip installation step")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload step")
    args = parser.parse_args()

    hf_token = args.hf_token.strip() or None
    if not hf_token and not args.skip_upload:
        import getpass
        hf_token = getpass.getpass("HF Token: ")

    log = setup_logging(log_file="/content/build.log")
    log.info(f"Build started — logging to /content/build.log")

    with timer() as total:
        setup_dir, comfy_dir = step_clone_repos()

        if not args.skip_install:
            step_install_deps(setup_dir)

        nodes_tar, env_tar = step_package_env()

        if not args.skip_upload and hf_token:
            step_upload_hf(nodes_tar, env_tar, hf_token)

    log.info("")
    log.info(f"{Color.OKGREEN}Build complete in {total.elapsed:.0f}s ({total.elapsed / 60:.1f}min){Color.ENDC}")
    log.info(f"Log saved to /content/build.log")


if __name__ == "__main__":
    main()
