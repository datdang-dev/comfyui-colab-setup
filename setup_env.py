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
from comfyui_setup.nodes import tar_filter, _collect_and_merge_requirements
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


def get_latest_comfyui_tag():
    """Fetch the latest release tag (v*.*.*) from the ComfyUI remote repository."""
    log = setup_logging()
    try:
        import re
        # Query remote tags list
        res = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", COMFYUI_REPO],
            capture_output=True, text=True, check=True, timeout=15
        )
        tags = []
        for line in res.stdout.splitlines():
            m = re.search(r"refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)$", line)
            if m:
                tags.append(m.group(1))
        if tags:
            # Natural sort for version numbers
            def tag_key(t):
                return [int(x) for x in t.strip("v").split(".")]
            tags.sort(key=tag_key)
            latest = tags[-1]
            log.info(f"Latest ComfyUI release tag found: {latest}")
            return latest
    except Exception as e:
        log.warning(f"Failed to fetch latest ComfyUI tag remotely: {e}")
    return ""


# ── Step 1: Clone repos ──
def step_clone_repos(comfy_version=""):
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

    # Resolve comfy_version: default to latest release tag if not specified or set to latest_release
    if not comfy_version or comfy_version == "latest_release":
        log.info("Resolving ComfyUI version to latest release tag...")
        comfy_version = get_latest_comfyui_tag()
        if not comfy_version:
            log.info("Could not resolve latest release tag. Defaulting to master branch.")

    # ComfyUI
    comfy_dir = WORKSPACE / "ComfyUI"
    if not comfy_dir.exists():
        if comfy_version:
            log.info(f"Cloning ComfyUI at version/branch/commit '{comfy_version}'...")
            # Try shallow cloning branch/tag first
            r = subprocess.run(f"git clone --depth=1 --branch {comfy_version} {COMFYUI_REPO} {comfy_dir}", shell=True)
            if r.returncode != 0:
                log.info(f"Shallow clone failed. Cloning full repo and checking out '{comfy_version}'...")
                run_cmd(f"git clone {COMFYUI_REPO} {comfy_dir}")
                run_cmd(f"git checkout {comfy_version}", cwd=str(comfy_dir))
        else:
            log.info("Cloning ComfyUI (latest master branch)...")
            run_cmd(f"git clone --depth=1 {COMFYUI_REPO} {comfy_dir}")
    else:
        if comfy_version:
            log.info(f"ComfyUI exists, checking out '{comfy_version}'...")
            run_cmd("git fetch --all", cwd=str(comfy_dir), quiet=True)
            run_cmd(f"git checkout {comfy_version}", cwd=str(comfy_dir))
        else:
            log.info("ComfyUI exists, pulling updates...")
            run_cmd("git pull", cwd=str(comfy_dir), quiet=True)

    # Log and pin the exact checked-out commit hash
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(comfy_dir), capture_output=True, text=True, check=True
        )
        commit_hash = res.stdout.strip()
        log.info(f"ComfyUI checked out at commit: {commit_hash}")
        # Save commit hash for verification in run session
        (comfy_dir / "comfyui_commit.txt").write_text(f"{commit_hash}\n", encoding="utf-8")
    except Exception as e:
        log.warning(f"Could not determine ComfyUI commit hash: {e}")

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

    # Install ComfyUI core requirements to compile/cache in site-packages
    comfy_dir = WORKSPACE / "ComfyUI"
    comfy_req = comfy_dir / "requirements.txt"
    if comfy_req.exists():
        log.info("Installing ComfyUI core requirements...")
        run_cmd(f"pip install -q -r {comfy_req}")

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

        print(f"  [{i:2d}/{len(nodes)}] {name}...", end="", flush=True)
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
            print(f"  {Color.OKGREEN}ok{Color.ENDC}")
            log.info(f"  [{i:2d}/{len(nodes)}] {name}... ok")
        else:
            fail += 1
            err = r.stderr.strip().splitlines()[-1] if r.stderr else f"exit {r.returncode}"
            print(f"  {Color.FAIL}FAIL: {err}{Color.ENDC}")
            log.info(f"  [{i:2d}/{len(nodes)}] {name}... FAIL: {err}")

    # Node pip deps — collect, merge, and install in single call
    log.info("Installing node dependencies...")
    req_files = []
    for p in sorted(nodes_dir.iterdir()):
        if p.is_dir():
            req = p / "requirements.txt"
            if req.exists():
                req_files.append(req)

    if req_files:
        import tempfile
        merged_lines, conflicts, all_reqs = _collect_and_merge_requirements(req_files)
        total_pkgs = len(all_reqs)
        log.info(f"  Collected {total_pkgs} unique packages from {len(req_files)} nodes")

        if conflicts:
            log.info(f"  {len(conflicts)} packages have multiple version constraints:")
            for pkg_name, specs in conflicts[:10]:
                spec_str = ", ".join(f"{node} wants {s}" for node, s in specs)
                log.info(f"    {pkg_name}: {spec_str}")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="merged_req_") as tmp:
            tmp.write("\n".join(merged_lines) + "\n")
            tmp_path = tmp.name

        log.info(f"  Installing merged requirements (single pip call)...")
        # Stream pip output live — force progress bar even when piped
        env = os.environ.copy()
        env["PIP_PROGRESS"] = "always"

        proc = subprocess.Popen(
            f"pip install --no-cache-dir --progress-bar=on -r {tmp_path}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        # Heartbeat: show we're alive every 30s while pip runs
        start_time = time.time()
        pip_output = []

        import select as _select
        while True:
            # Check if process finished
            ret = proc.poll()
            if ret is not None:
                # Drain remaining output
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        log.info(f"    {line}")
                        pip_output.append(line)
                break

            # Wait up to 30s for output
            ready, _, _ = _select.select([proc.stdout], [], [], 30)
            if ready:
                line = proc.stdout.readline().rstrip()
                if line:
                    log.info(f"    {line}")
                    pip_output.append(line)
            else:
                # Heartbeat — show elapsed time so user knows it's alive
                elapsed = time.time() - start_time
                log.info(f"    ... pip still running ({elapsed:.0f}s elapsed)")

        proc.wait(timeout=10)

        if proc.returncode != 0:
            for line in pip_output[-10:]:
                log.warning(f"    {line}")
            log.warning(f"  {Color.FAIL}pip install failed — see errors above{Color.ENDC}")
        else:
            log.info(f"  {Color.OKGREEN}Node dependencies installed ({total_pkgs} packages).{Color.ENDC}")

        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    else:
        log.info("  No node requirements.txt found.")

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

    # Write metadata.json
    commit_file = comfy_dir / "comfyui_commit.txt"
    commit_hash = ""
    if commit_file.exists():
        commit_hash = commit_file.read_text().strip()

    import json
    import datetime
    meta_data = {
        "comfyui_commit": commit_hash,
        "built_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    meta_json = WORKSPACE / "metadata.json"
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, indent=2)
    log.info(f"  Created metadata.json with commit {commit_hash}")

    # Generate and write download_list.yaml from config.yaml if models are configured
    try:
        from comfyui_setup.config import get_default_models
        default_models = get_default_models()
        if default_models:
            import yaml
            dl_yaml = WORKSPACE / "download_list.yaml"
            with open(dl_yaml, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_models, f, default_flow_style=False)
            log.info(f"  Created download_list.yaml with {len(default_models)} default models.")
    except Exception as e:
        log.warning(f"  Could not generate default models list: {e}")

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
        log.info("  [2/2] Packaging Python environment (site-packages only)...")
        with timer() as t:
            # Pack site-packages folder
            cmd = (
                f"tar -cf - -C {site_packages.parent} {site_packages.name} | {method} -4 > {env_tar}"
            )
            stop = Event()
            reporter = Thread(
                target=_progress_reporter, args=(env_tar, stop, "comfyui-env"), daemon=True
            )
            reporter.start()
            try:
                subprocess.run(cmd, shell=True, check=True)
            finally:
                stop.set()
                reporter.join(timeout=2)
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
def step_upload_hf(nodes_tar, env_tar, hf_token, models_tar=None):
    log = setup_logging()
    print_header("STEP 4: Upload to HuggingFace")

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=ENV_REPO, repo_type="dataset", token=hf_token, exist_ok=True)

    meta_json = WORKSPACE / "metadata.json"
    dl_yaml = WORKSPACE / "download_list.yaml"
    files_to_upload = [
        (str(nodes_tar), "custom_nodes.tar.gz"),
        (str(env_tar), "comfyui-env.tar.gz"),
    ]
    if meta_json.exists():
        files_to_upload.append((str(meta_json), "metadata.json"))
    if dl_yaml.exists():
        files_to_upload.append((str(dl_yaml), "download_list.yaml"))
    if models_tar and Path(models_tar).exists():
        files_to_upload.append((str(models_tar), "comfyui-models.tar.gz"))

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

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(upload_one, local, remote) for local, remote in files_to_upload]
        for future in futures:
            future.result()

    log.info(f"{Color.OKGREEN}Upload complete.{Color.ENDC}")
    log.info(f"  Dataset: https://huggingface.co/datasets/{ENV_REPO}")


def step_download_and_package_models(setup_dir, comfy_dir, hf_token):
    """Download models from download_list.json and package them into a compressed tarball."""
    log = setup_logging()
    print_header("STEP 2.5: Download and Package Models")

    dl_file = setup_dir / "download_list.yaml"
    if not dl_file.exists():
        log.info("No download_list.yaml found in setup repo, skipping models prebuild.")
        return None

    # Load download_list.yaml using PyYAML
    import yaml
    try:
        with open(dl_file, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as e:
        log.error(f"Failed to parse download_list.yaml: {e}")
        return None

    # Flatten grouped list if structured as a dictionary
    download_list = []
    if isinstance(raw_data, list):
        download_list = raw_data
    elif isinstance(raw_data, dict):
        for val in raw_data.values():
            if isinstance(val, list):
                download_list.extend(val)

    if not download_list:
        log.info("download_list.yaml has no active models, skipping models prebuild.")
        return None

    # Enable hf_transfer for high speed download
    run_cmd("pip install hf_transfer -q", quiet=True)
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    # Download all models to their mapped destination dirs (usually inside ComfyUI/models/)
    log.info(f"Downloading {len(download_list)} models...")
    from comfyui_setup.models import download_all
    download_all(download_list, auth_token=hf_token)

    # Detect compression
    method, suffix = detect_compression()
    models_tar = WORKSPACE / f"comfyui-models{suffix}"

    log.info("Packaging downloaded models into prebuilt archive...")
    with timer() as t:
        cmd = f"tar -cf - -C {comfy_dir} models | {method} -4 > {models_tar}"
        stop = Event()
        reporter = Thread(
            target=_progress_reporter, args=(models_tar, stop, "comfyui-models"), daemon=True
        )
        reporter.start()
        try:
            subprocess.run(cmd, shell=True, check=True)
        finally:
            stop.set()
            reporter.join(timeout=2)

    size = models_tar.stat().st_size / (1024 * 1024)
    log.info(f"  {Color.OKGREEN}comfyui-models{suffix}: {size:.0f}MB ({t.elapsed:.0f}s){Color.ENDC}")

    return models_tar


# ── Unified CLI Integration ──

def run_fetch(repo_id, output_file):
    """Fetch model list from HF dataset and write to download_list.yaml."""
    log = setup_logging()
    log.info(f"Fetching file list from HF dataset repository: {repo_id}...")
    from huggingface_hub import HfApi
    api = HfApi()
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    except Exception as e:
        log.error(f"Error fetching repo files: {e}")
        sys.exit(1)

    url_prefix = f"https://huggingface.co/datasets/{repo_id}/resolve/main"
    
    # Custom category mapping
    mapping = {
        "checkpoint": "checkpoints",
        "clip_vision": "clip_vision",
        "diffusion_models": "diffusion_models",
        "embedding": "embeddings",
        "ipadapters": "ipadapter",
        "lora": "loras",
        "text_encoders": "text_encoders",
        "ultralytics/bbox": "ultralytics/bbox",
        "upscalers": "upscale_models",
        "vae": "vae"
    }

    grouped = {}
    for prefix, target_dir in mapping.items():
        group_name = target_dir.replace("/", "_")
        grouped[group_name] = []

    for f in sorted(files):
        f_lower = f.lower()
        for prefix, target_dir in mapping.items():
            if f_lower.startswith(prefix + "/"):
                group_name = target_dir.replace("/", "_")
                filename = os.path.basename(f)
                
                # Check for subdirectories under the prefix
                sub_dir = os.path.dirname(f[len(prefix) + 1:])
                dest_dir = f"/content/ComfyUI/models/{target_dir}"
                if sub_dir:
                    dest_dir = os.path.join(dest_dir, sub_dir).replace("\\", "/")

                grouped[group_name].append({
                    "filename": filename,
                    "url": f"{url_prefix}/{f}",
                    "dest_dir": dest_dir
                })
                break

    # Clean up empty groups
    grouped = {k: v for k, v in grouped.items() if v}

    import re
    lines = []
    for category in sorted(grouped.keys()):
        lines.append(f"{category}:")
        for item in grouped[category]:
            lines.append(f"  - dest_dir: {item['dest_dir']}")
            lines.append(f"    filename: {item['filename']}")
            lines.append(f"    url: {item['url']}")
            lines.append("")  # Empty line after item
        lines.append("")  # Empty line after category
        
    content = "\n".join(lines).strip() + "\n"
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # normalize spacing

    try:
        from pathlib import Path
        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as out_f:
            out_f.write(content)
        log.info(f"{Color.OKGREEN}Successfully generated structured {output_path} with {sum(len(v) for v in grouped.values())} files across {len(grouped)} categories.{Color.ENDC}")
    except Exception as e:
        log.error(f"Failed to write output file: {e}")
        sys.exit(1)


def run_install(args):
    """Run standard comfyui-setup installation process."""
    from comfyui_setup import config
    from comfyui_setup.main import _run
    
    # Init logging with file handler
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


# ── Main ──
def main():
    # Handle backward compatibility: if first argument is not a known subcommand and starts with '-', insert 'build'
    if len(sys.argv) > 1 and sys.argv[1].startswith("-") and sys.argv[1] not in ["-h", "--help"]:
        sys.argv.insert(1, "build")

    parser = argparse.ArgumentParser(description="ComfyUI Colab Setup CLI Consolidation Utility")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Consolidated command to execute")

    # Command: build (packages environment)
    parser_build = subparsers.add_parser("build", help="Build pre-built environment and package it")
    parser_build.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser_build.add_argument("--skip-install", action="store_true", help="Skip dependency installation step")
    parser_build.add_argument("--skip-upload", action="store_true", help="Skip HuggingFace uploading step")
    parser_build.add_argument("--comfy-version", default="", help="Specific ComfyUI git version to checkout")

    # Command: install (restores or installs ComfyUI environment)
    parser_install = subparsers.add_parser("install", help="Run CLI installation wrapper to setup ComfyUI")
    parser_install.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser_install.add_argument("--repo-id", default="datsss/my-dataset", help="HF Dataset source repo")
    parser_install.add_argument("--repo-type", default="dataset", help="HF repository type")
    parser_install.add_argument("--max-parallel", type=int, default=4, help="Maximum concurrent downloads")
    parser_install.add_argument("--workspace", default="/content", help="WORKSPACE directory path")
    parser_install.add_argument("--custom-nodes", default="", help="Comma-separated custom nodes to clone")
    parser_install.add_argument("--use-prebuilt", action="store_true", help="Download and extract pre-built packages")
    parser_install.add_argument("--env-repo", default="datsss/comfyui-env", help="HF target environment repository")
    parser_install.add_argument("--skip-nodes", action="store_true", help="Skip cloning custom nodes")
    parser_install.add_argument("--skip-select", action="store_true", help="Skip models selective wizard")
    parser_install.add_argument("--skip-download", action="store_true", help="Skip downloading files")

    # Command: fetch (updates download_list.yaml)
    parser_fetch = subparsers.add_parser("fetch", help="Query HF dataset models to rebuild download_list.yaml")
    parser_fetch.add_argument("--repo-id", default="datsss/my-dataset", help="HF source dataset repository ID")
    parser_fetch.add_argument("--output", default="download_list.yaml", help="Path to output YAML file")

    args = parser.parse_args()

    if args.command == "fetch":
        run_fetch(args.repo_id, args.output)
        return

    if args.command == "install":
        run_install(args)
        return

    if args.command == "build":
        hf_token = args.hf_token.strip() or None
        if not hf_token and not args.skip_upload:
            import getpass
            hf_token = getpass.getpass("HF Token: ")

        log = setup_logging(log_file="/content/build.log")
        log.info(f"Build started — logging to /content/build.log")

        with timer() as total:
            setup_dir, comfy_dir = step_clone_repos(comfy_version=args.comfy_version.strip())

            if not args.skip_install:
                step_install_deps(setup_dir)

            # Download and package models if download_list.yaml is present
            models_tar = step_download_and_package_models(setup_dir, comfy_dir, hf_token)

            nodes_tar, env_tar = step_package_env()

            if not args.skip_upload and hf_token:
                step_upload_hf(nodes_tar, env_tar, hf_token, models_tar)

        log.info("")
        log.info(f"{Color.OKGREEN}Build complete in {total.elapsed:.0f}s ({total.elapsed / 60:.1f}min){Color.ENDC}")
        log.info(f"Log saved to /content/build.log")


if __name__ == "__main__":
    main()
