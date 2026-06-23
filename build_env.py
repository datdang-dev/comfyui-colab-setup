"""Build script — run on Colab to create pre-built environment.

Usage:
    1. Open this notebook in Colab
    2. Run Cell 1 to install everything
    3. Run Cell 2 to package and upload to HF
    4. The uploaded env can then be used by the main notebook
"""

# %% [markdown]
# # 🔨 Build Pre-built Environment
# Run this ONCE to create the environment archive.
# After upload, use the main notebook with `--use-prebuilt`.

# %%
#@title 📦 Step 1: Install Everything
import subprocess
import os
import sys
from pathlib import Path

WORKSPACE = Path("/content")
COMFYUI_DIR = WORKSPACE / "ComfyUI"
CUSTOM_NODES_DIR = WORKSPACE / "custom_nodes"

# Clone ComfyUI
if not COMFYUI_DIR.exists():
    print("📥 Cloning ComfyUI...")
    subprocess.run(f"git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git {COMFYUI_DIR}", shell=True, check=True)

# Install core requirements
print("📦 Installing ComfyUI core deps...")
subprocess.run(f"pip install -q -r {COMFYUI_DIR / 'requirements.txt'}", shell=True, check=True)

# Install hf_transfer
subprocess.run("pip install -q hf_transfer huggingface_hub", shell=True, check=True)

# Clone all custom nodes
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

CUSTOM_NODES_DIR.mkdir(exist_ok=True)
print(f"\n🧩 Cloning {len(CUSTOM_NODES)} custom nodes...")

for i, url in enumerate(CUSTOM_NODES, 1):
    name = url.split("/")[-1]
    dest = CUSTOM_NODES_DIR / name
    if not dest.exists():
        print(f"  [{i:2d}/{len(CUSTOM_NODES)}] ⬇️  {name}...", end=" ", flush=True)
        r = subprocess.run(f"git clone --depth=1 {url}", shell=True, cwd=CUSTOM_NODES_DIR,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✓" if r.returncode == 0 else "✗")
    else:
        print(f"  [{i:2d}/{len(CUSTOM_NODES)}] 🔄 {name}... exists")

# Install all node dependencies
print("\n📦 Installing node dependencies...")
pip_args = []
for node_path in CUSTOM_NODES_DIR.iterdir():
    if node_path.is_dir():
        req = node_path / "requirements.txt"
        if req.exists():
            pip_args.append(f"-r {req}")

if pip_args:
    # Install in batches to avoid timeout
    batch_size = 5
    for i in range(0, len(pip_args), batch_size):
        batch = pip_args[i:i+batch_size]
        print(f"  Installing batch {i//batch_size + 1}...")
        subprocess.run(f"pip install -q {' '.join(batch)}", shell=True,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("\n✅ All dependencies installed!")

# %%
#@title 📤 Step 2: Package & Upload to HF
import subprocess
import os
from pathlib import Path
from huggingface_hub import HfApi

HF_TOKEN = os.environ.get("HF_TOKEN", "")
WORKSPACE = Path("/content")
COMFYUI_DIR = WORKSPACE / "ComfyUI"
CUSTOM_NODES_DIR = WORKSPACE / "custom_nodes"

# Package custom_nodes
print("📦 Packaging custom_nodes...")
subprocess.run(f"tar -czf /content/custom_nodes.tar.gz -C {WORKSPACE} custom_nodes", shell=True, check=True)

# Package Python site-packages (the heavy deps)
print("📦 Packaging Python environment...")
subprocess.run(f"tar -czf /content/env.tar.gz -C /usr/local/lib python3.10/dist-packages", shell=True, check=True)

# Get sizes
env_size = os.path.getsize("/content/env.tar.gz") / (1024*1024)
nodes_size = os.path.getsize("/content/custom_nodes.tar.gz") / (1024*1024)
print(f"\n📊 Package sizes:")
print(f"   env.tar.gz: {env_size:.0f}MB")
print(f"   custom_nodes.tar.gz: {nodes_size:.0f}MB")

# Upload to HF
print("\n📤 Uploading to HF...")
api = HfApi()

# Create dataset repo
repo_id = "datsss/comfyui-env"
try:
    api.create_repo(repo_id=repo_id, repo_type="dataset", token=HF_TOKEN, exist_ok=True)
    print(f"  📁 Dataset repo: {repo_id}")
except Exception as e:
    print(f"  ⚠️  Repo exists or error: {e}")

# Upload files
print("  ⬆️  Uploading env.tar.gz...")
api.upload_file(
    path_or_fileobj="/content/env.tar.gz",
    path_in_repo="env.tar.gz",
    repo_id=repo_id,
    repo_type="dataset",
    token=HF_TOKEN,
)
print("  ✅ env.tar.gz uploaded")

print("  ⬆️  Uploading custom_nodes.tar.gz...")
api.upload_file(
    path_or_fileobj="/content/custom_nodes.tar.gz",
    path_in_repo="custom_nodes.tar.gz",
    repo_id=repo_id,
    repo_type="dataset",
    token=HF_TOKEN,
)
print("  ✅ custom_nodes.tar.gz uploaded")

print(f"\n{'='*55}")
print(f"  ✅ Build complete!")
print(f"  📁 Dataset: https://huggingface.co/datasets/{repo_id}")
print(f"  📊 Total: {env_size + nodes_size:.0f}MB")
print(f"{'='*55}\n")
