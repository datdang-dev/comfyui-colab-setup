"""Main install script — called from Colab notebook.

Usage:
    python install.py --hf-token=xxx --repo-id=datsss/my-dataset --max-parallel=8

Flow:
    1. Clone ComfyUI core (if not exists)
    2. Install custom nodes (subprocess, background)
    3. Interactive model selection
    4. Download models (hf_transfer, parallel)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


# ── Config ──
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
WORKSPACE = "/content"

CUSTOM_NODES = [
    "https://github.com/ltdrdata/ComfyUI-Manager",
    "https://github.com/cubiq/ComfyUI_IPAdapter_plus",
    "https://github.com/Fannovel16/comfyui_controlnet_aux",
    "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
    "https://github.com/pythongosssss/ComfyUI-Custom-Scripts",
    "https://github.com/rgthree/rgthree-comfy",
    "https://github.com/kijai/ComfyUI-KJNodes",
    "https://github.com/jags111/efficiency-nodes-comfyui",
    "https://github.com/cubiq/ComfyUI_essentials",
    "https://github.com/giriss/comfy-image-saver",
    "https://github.com/ltdrdata/ComfyUI-Impact-Subpack",
    "https://github.com/MNeMoNiCuZ/ComfyUI-mnemic-nodes",
    "https://github.com/comfy-deploy/comfyui-llm-toolkit",
    "https://github.com/bradsec/ComfyUI_ResolutionSelector",
    "https://github.com/pydn/ComfyUI-to-Python-Extension",
    "https://github.com/ssitu/ComfyUI_UltimateSDUpscale",
]

CATEGORIES = {
    "checkpoint":       "checkpoints",
    "lora":             "loras",
    "embedding":        "embeddings",
    "ipadapters":       "ipadapter",
    "clip_vision":      "clip_vision",
    "upscalers":        "upscale_models",
    "text_encoders":    "text_encoders",
    "vae":              "vae",
    "diffusion_models": "diffusion_models",
}

DOWNLOAD_LIST_FILE = "/content/download_list.json"


# ── UI ──
class Color:
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def run_cmd(cmd, cwd=None, quiet=False):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd,
                       stdout=subprocess.DEVNULL if quiet else None,
                       stderr=subprocess.DEVNULL if quiet else None)
        return True
    except subprocess.CalledProcessError:
        return False


# ── Step 1: Clone ComfyUI ──
def clone_comfyui(workspace):
    comfy_dir = workspace / "ComfyUI"
    if not comfy_dir.exists():
        print(f"\n  {Color.OKBLUE}📥 Cloning ComfyUI...{Color.ENDC}")
        run_cmd(f"git clone --depth=1 {COMFYUI_REPO}", cwd=workspace)
        req = comfy_dir / "requirements.txt"
        if req.exists():
            run_cmd(f"pip install -q -r {req}")
        (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
        print(f"  {Color.OKGREEN}✅ ComfyUI core ready{Color.ENDC}")
    else:
        print(f"  {Color.OKBLUE}🔄 ComfyUI already cloned{Color.ENDC}")
    return comfy_dir





def load_prebuilt(workspace, auth_token, env_repo="datsss/comfyui-env"):
    """Download and extract pre-built environment from HF."""
    from huggingface_hub import hf_hub_download

    comfy_dir = workspace / "ComfyUI"
    custom_nodes_dir = workspace / "custom_nodes"

    print(f"\n  {Color.OKBLUE}📥 Loading pre-built environment from {env_repo}...{Color.ENDC}")

    # Download custom_nodes
    print(f"  ⬇️  Downloading custom_nodes.tar.gz...")
    nodes_archive = hf_hub_download(
        repo_id=env_repo,
        filename="custom_nodes.tar.gz",
        repo_type="dataset",
        token=auth_token,
    )
    print(f"  📦 Extracting custom_nodes...")
    subprocess.run(f"tar -xzf {nodes_archive} -C {workspace}", shell=True, check=True)
    print(f"  {Color.OKGREEN}✅ Custom nodes ready{Color.ENDC}")

    # Download env
    print(f"  ⬇️  Downloading env.tar.gz...")
    env_archive = hf_hub_download(
        repo_id=env_repo,
        filename="env.tar.gz",
        repo_type="dataset",
        token=auth_token,
    )
    print(f"  📦 Extracting Python environment...")
    subprocess.run(f"tar -xzf {env_archive} -C /usr/local/lib", shell=True, check=True)
    print(f"  {Color.OKGREEN}✅ Python environment ready{Color.ENDC}")

    return comfy_dir
# ── Step 2: Install Nodes (background subprocess) ──
def start_nodes(comfy_dir, extra_nodes=None):
    nodes = CUSTOM_NODES + (extra_nodes or [])
    nodes_dir = comfy_dir / "custom_nodes"
    nodes_dir.mkdir(exist_ok=True)

    # Generate install script
    script = f'''import subprocess, os
from pathlib import Path

nodes_dir = Path("{nodes_dir}")
ok = 0
fail = 0
total = {len(nodes)}

print("\\n  🧩 Installing custom nodes...")
for i, url in enumerate({nodes!r}, 1):
    name = url.split("/")[-1]
    dest = nodes_dir / name
    if not dest.exists():
        print(f"  [{{i:2d}}/{{total}}] ⬇️  {{name}}...", end=" ", flush=True)
        r = subprocess.run(f"git clone --depth=1 {{url}}", shell=True, cwd=str(nodes_dir),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print("✓")
            ok += 1
        else:
            print("✗")
            fail += 1
    else:
        print(f"  [{{i:2d}}/{{total}}] 🔄 {{name}}...", end=" ", flush=True)
        r = subprocess.run("git pull", shell=True, cwd=str(dest),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print("ok")
            ok += 1
        else:
            print("skip")

# Install pip deps
pip_args = []
for p in nodes_dir.iterdir():
    if p.is_dir():
        req = p / "requirements.txt"
        if req.exists():
            pip_args.append(f"-r {{req}}")

if pip_args:
    print(f"\\n  📦 Installing {{len(pip_args)}} node dependencies...", end=" ", flush=True)
    subprocess.run(f"pip install -q {{' '.join(pip_args)}}", shell=True,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓")

print(f"\\n  ✅ Nodes: {{ok}}/{{total}} installed")
'''

    script_path = "/tmp/_install_nodes.py"
    with open(script_path, "w") as f:
        f.write(script)

    print(f"  {Color.OKBLUE}🧩 Starting node install in background...{Color.ENDC}")
    print(f"     (You can select models while nodes install)\n")

    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    return proc.pid


# ── Step 3: Select Models ──
def select_models(repo_id, repo_type, workspace, auth_token):
    from huggingface_hub import HfApi
    from collections import defaultdict

    api = HfApi()
    base_dir = str(workspace / "ComfyUI" / "models")

    print(f"\n  {Color.OKBLUE}🔍 Fetching files from {repo_id} ({repo_type})...{Color.ENDC}")
    all_files = api.list_repo_files(repo_id=repo_id, token=auth_token, repo_type=repo_type)

    # URL prefix
    url_prefix = (
        f"https://huggingface.co/datasets/{repo_id}"
        if repo_type == "dataset"
        else f"https://huggingface.co/{repo_id}"
    )

    # Categorize
    cat_dirs = {}
    for prefix, dirname in CATEGORIES.items():
        cat_dirs[prefix] = os.path.join(base_dir, dirname)
        os.makedirs(cat_dirs[prefix], exist_ok=True)

    categorized = defaultdict(list)
    for f in all_files:
        f_lower = f.lower()
        for prefix, dest in cat_dirs.items():
            if f_lower.startswith(f"{prefix}/"):
                categorized[prefix].append({
                    "url": f"{url_prefix}/resolve/main/{f}",
                    "dest_dir": dest,
                    "filename": os.path.basename(f),
                })
                break

    # Display tree
    print(f"\n  {Color.BOLD}{Color.OKCYAN}📂 Available models:{Color.ENDC}\n")
    counter = 1
    cat_indexes = {}
    for cat in CATEGORIES:
        items = categorized.get(cat, [])
        if not items:
            continue
        print(f"  📁 {cat}/ ({len(items)} files)")
        cat_start = counter
        for item in items:
            print(f"     [{Color.OKGREEN}{counter:2d}{Color.ENDC}] {item['filename']}")
            counter += 1
        cat_indexes[cat] = list(range(cat_start, counter))
        print()

    # Interactive selection
    print(f"  {'─'*50}")
    print(f"  📥 SELECT MODELS TO DOWNLOAD")
    print(f"  {'─'*50}\n")
    print(f"  For each category, enter file numbers (comma separated)")
    print(f"  or leave blank to download ALL in that category.\n")

    filtered = []
    for cat in CATEGORIES:
        idx_list = cat_indexes.get(cat, [])
        if not idx_list:
            continue

        items = categorized[cat]
        idx_str = ",".join(map(str, idx_list))
        user_input = input(f"  {cat} ({len(idx_list)} files): {idx_str}\n  → Select files (blank=all): ").strip()

        if user_input == "":
            filtered.extend(items)
        else:
            try:
                picks = [int(x.strip()) for x in user_input.split(",")]
                for pick in picks:
                    if pick in idx_list:
                        cat_items = categorized[cat]
                        cat_start = idx_list[0]
                        item_idx = pick - cat_start
                        if 0 <= item_idx < len(cat_items):
                            filtered.append(cat_items[item_idx])
                    else:
                        print(f"    {Color.WARNING}⚠️  {pick} not in {cat}, skipped{Color.ENDC}")
            except ValueError:
                print(f"    {Color.WARNING}⚠️  Invalid input, selecting all {cat}{Color.ENDC}")
                filtered.extend(items)
        print()

    # Save download list
    with open(DOWNLOAD_LIST_FILE, "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"  {Color.OKGREEN}✅ {len(filtered)} files selected → saved to {DOWNLOAD_LIST_FILE}{Color.ENDC}")
    return filtered


# ── Step 4: Download Models ──
def download_models(auth_token, max_parallel):
    if not os.path.exists(DOWNLOAD_LIST_FILE):
        print(f"  {Color.WARNING}⚠️  No download list found.{Color.ENDC}")
        return

    with open(DOWNLOAD_LIST_FILE) as f:
        download_list = json.load(f)

    if not download_list:
        print(f"  ℹ️  No files to download.")
        return

    # Pre-check
    to_download = []
    skipped = 0
    for item in download_list:
        dest = os.path.join(item["dest_dir"], item["filename"])
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            skipped += 1
        else:
            os.makedirs(item["dest_dir"], exist_ok=True)
            to_download.append(item)

    if skipped:
        print(f"  ⏭️  Skipping {skipped} existing files")

    if not to_download:
        print(f"  {Color.OKGREEN}✅ All {len(download_list)} files already downloaded!{Color.ENDC}")
        return

    print(f"  🚀 Downloading {len(to_download)} files ({max_parallel} parallel)...\n")

    # Install hf_transfer
    run_cmd("pip install hf_transfer -q", quiet=True)
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    import concurrent.futures
    from huggingface_hub import hf_hub_download

    def download_one(item):
        url = item["url"]
        if "/datasets/" in url:
            repo_part = url.split("/datasets/")[1].split("/resolve/")[0]
            repo_type = "dataset"
        else:
            repo_part = url.split("huggingface.co/")[1].split("/resolve/")[0]
            repo_type = "model"
        file_path = url.split("/resolve/main/")[1]
        return hf_hub_download(
            repo_id=repo_part, filename=file_path, repo_type=repo_type,
            token=auth_token, local_dir=item["dest_dir"],
        )

    ok = 0
    fail = 0
    total = len(to_download)
    start_time = time.time()

    def dl_with_log(item):
        nonlocal ok, fail
        fname = item["filename"]
        try:
            download_one(item)
            ok += 1
            elapsed = time.time() - start_time
            speed = ok / elapsed if elapsed > 0 else 0
            eta = (total - ok - fail) / speed if speed > 0 else 0
            print(f"  [{ok+fail:3d}/{total}] {Color.OKGREEN}✓{Color.ENDC} {fname}  "
                  f"({speed:.1f}/s, ETA {int(eta)}s)")
        except Exception as e:
            fail += 1
            print(f"  [{ok+fail:3d}/{total}] {Color.FAIL}✗{Color.ENDC} {fname}: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as pool:
        list(pool.map(dl_with_log, to_download))

    elapsed = time.time() - start_time
    print(f"\n  {'─'*50}")
    if fail == 0:
        print(f"  {Color.OKGREEN}✅ Done: {ok} files in {elapsed:.1f}s ({elapsed/60:.1f}min){Color.ENDC}")
    else:
        print(f"  {Color.WARNING}⚠️  Done: {ok} ok, {fail} failed in {elapsed:.1f}s{Color.ENDC}")


# ── Main ──
def main():
    parser = argparse.ArgumentParser(description="ComfyUI Colab Setup")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--repo-id", default="datsss/my-dataset")
    parser.add_argument("--repo-type", default="dataset")
    parser.add_argument("--max-parallel", type=int, default=8)
    parser.add_argument("--workspace", default=WORKSPACE)
    parser.add_argument("--skip-nodes", action="store_true")
    parser.add_argument("--skip-select", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    # Resolve auth token
    auth_token = args.hf_token if args.hf_token.strip() else None
    if not auth_token:
        auth_token = os.environ.get("HF_TOKEN", "").strip() or None
    if not auth_token:
        print(f"  {Color.WARNING}⚠️  No HF_TOKEN — private repos will not be accessible{Color.ENDC}")

    workspace = Path(args.workspace)

    # Step 1: Clone ComfyUI (or load prebuilt)
    if args.use_prebuilt:
        comfy_dir = load_prebuilt(workspace, auth_token, args.env_repo)
        # Skip node install (already in prebuilt)
        args.skip_nodes = True
    else:
        comfy_dir = clone_comfyui(workspace)

    # Step 2: Start nodes in background
    nodes_pid = None
    if not args.skip_nodes:
        print(f"\n{'='*55}")
        print(f"  🧩 INSTALL CUSTOM NODES (background)")
        print(f"{'='*55}")
        nodes_pid = start_nodes(comfy_dir)

    # Step 3: Select models (nodes installing in background)
    if not args.skip_select:
        print(f"\n{'='*55}")
        print(f"  📥 SELECT MODELS")
        print(f"{'='*55}")
        select_models(args.repo_id, args.repo_type, workspace, auth_token)

    # Step 4: Download models
    if not args.skip_download:
        print(f"\n{'='*55}")
        print(f"  📦 DOWNLOAD MODELS")
        print(f"{'='*55}")
        download_models(auth_token, args.max_parallel)

    # Step 5: Wait for nodes
    if nodes_pid:
        print(f"\n  ⏳ Waiting for node installation...")
        while True:
            result = subprocess.run(f"ps -p {nodes_pid}", shell=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                break
            time.sleep(2)
        print(f"  {Color.OKGREEN}✅ Nodes installed{Color.ENDC}")

    print(f"\n  {Color.OKGREEN}{'='*55}{Color.ENDC}")
    print(f"  {Color.OKGREEN}✅ Setup complete!{Color.ENDC}")
    print(f"  {Color.OKGREEN}{'='*55}{Color.ENDC}\n")


if __name__ == "__main__":
    main()
