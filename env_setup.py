# %% [markdown]
# <div style="padding: 24px; border-radius: 16px; background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; font-family: 'Outfit', -apple-system, sans-serif; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
#     <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">🔨 ComfyUI Environment Builder</h1>
#     <p style="margin: 8px 0 0 0; font-size: 15px; color: #A7F3D0;">Build pre-built environment for fast Colab setup</p>
#     <p style="margin: 4px 0 0 0; font-size: 13px; color: #6EE7B7;">Run this ONCE to create env archive. Then use main notebook with USE_PREBUILT=True.</p>
# </div>

# %% [markdown]
# <div style="border-left: 5px solid #10B981; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">Step 1: Install Everything</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Clone ComfyUI, install all dependencies (~10 min)</p>
# </div>

# %%
#@title 📦 Install ComfyUI + Nodes + Dependencies
import subprocess
import os
import sys
from pathlib import Path

WORKSPACE = Path("/content")
COMFYUI_DIR = WORKSPACE / "ComfyUI"
CUSTOM_NODES_DIR = WORKSPACE / "custom_nodes"

# ── Clone ComfyUI ──
if not COMFYUI_DIR.exists():
    print("📥 Cloning ComfyUI...")
    subprocess.run(f"git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git {COMFYUI_DIR}", shell=True, check=True)
else:
    print("🔄 ComfyUI exists, skipping clone")

# ── Install core requirements ──
print("\n📦 Installing ComfyUI core deps...")
subprocess.run(f"pip install -q -r {COMFYUI_DIR / 'requirements.txt'}", shell=True, check=True)
subprocess.run("pip install -q hf_transfer huggingface_hub", shell=True, check=True)

# ── Custom nodes to clone ──
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

# ── Clone nodes ──
CUSTOM_NODES_DIR.mkdir(exist_ok=True)
print(f"\n🧩 Cloning {len(CUSTOM_NODES)} custom nodes...")

cloned = 0
skipped = 0
for i, url in enumerate(CUSTOM_NODES, 1):
    name = url.split("/")[-1]
    dest = CUSTOM_NODES_DIR / name
    if not dest.exists():
        print(f"  [{i:2d}/{len(CUSTOM_NODES)}] ⬇️  {name}...", end=" ", flush=True)
        r = subprocess.run(f"git clone --depth=1 {url}", shell=True, cwd=CUSTOM_NODES_DIR,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✓" if r.returncode == 0 else "✗")
        if r.returncode == 0:
            cloned += 1
    else:
        print(f"  [{i:2d}/{len(CUSTOM_NODES)}] 🔄 {name}... exists")
        skipped += 1

print(f"\n  Cloned: {cloned}, Skipped: {skipped}")

# ── Install node dependencies ──
print("\n📦 Installing node dependencies...")
pip_args = []
for node_path in CUSTOM_NODES_DIR.iterdir():
    if node_path.is_dir():
        req = node_path / "requirements.txt"
        if req.exists():
            pip_args.append(f"-r {req}")

if pip_args:
    batch_size = 5
    for i in range(0, len(pip_args), batch_size):
        batch = pip_args[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(pip_args) + batch_size - 1) // batch_size
        print(f"  Batch {batch_num}/{total_batches}...")
        r = subprocess.run(f"pip install -q {' '.join(batch)}", shell=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            print(f"    ⚠️  Some packages failed (may be OK)")

print("\n✅ All dependencies installed!")
print(f"   ComfyUI: {COMFYUI_DIR}")
print(f"   Custom nodes: {len(list(CUSTOM_NODES_DIR.iterdir()))} nodes")

# %% [markdown]
# <div style="border-left: 5px solid #10B981; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">Step 2: Package & Upload</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Create archives and upload to HF (~2 min)</p>
# </div>

# %%
#@title 📤 Package & Upload to HF
import subprocess
import os
from pathlib import Path
from huggingface_hub import HfApi

HF_TOKEN=os.environ.get("HF_TOKEN", "")
WORKSPACE = Path("/content")
CUSTOM_NODES_DIR = WORKSPACE / "custom_nodes"

REPO_ID = "datsss/comfyui-env"  #@param {type:"string"}

# ── Package custom_nodes ──
print("📦 Packaging custom_nodes...")
r = subprocess.run(f"tar -czf /content/custom_nodes.tar.gz -C {WORKSPACE} custom_nodes", 
                  shell=True, check=True)

nodes_size = os.path.getsize("/content/custom_nodes.tar.gz") / (1024*1024)
print(f"  ✅ custom_nodes.tar.gz: {nodes_size:.0f}MB")

# ── Package Python env ──
print("\n📦 Packaging Python environment...")
# Find the right dist-packages path
import sysconfig
dist_path = sysconfig.get_path("purelib")  # e.g., /usr/lib/python3.10/dist-packages
if not os.path.exists(dist_path):
    dist_path = f"/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages"

print(f"  Path: {dist_path}")
r = subprocess.run(f"tar -czf /content/env.tar.gz -C {os.path.dirname(dist_path)} {os.path.basename(dist_path)}", 
                  shell=True, check=True)

env_size = os.path.getsize("/content/env.tar.gz") / (1024*1024)
print(f"  ✅ env.tar.gz: {env_size:.0f}MB")

# ── Upload to HF ──
print(f"\n📤 Uploading to {REPO_ID}...")
api = HfApi()

# Create repo
try:
    HF_TOKEN=os.environ.get("HF_TOKEN", "")
    print(f"  📁 Dataset ready: {REPO_ID}")
except Exception as e:
    print(f"  ⚠️  Repo: {e}")

# Upload custom_nodes
print("  ⬆️  Uploading custom_nodes.tar.gz...")
api.upload_file(
    path_or_fileobj="/content/custom_nodes.tar.gz",
    path_in_repo="custom_nodes.tar.gz",
    repo_id=REPO_ID,
    repo_type="dataset",
HF_TOKEN=os.environ.get("HF_TOKEN", "")
)
print("  ✅ custom_nodes.tar.gz uploaded")

# Upload env
print("  ⬆️  Uploading env.tar.gz...")
api.upload_file(
    path_or_fileobj="/content/env.tar.gz",
    path_in_repo="env.tar.gz",
    repo_id=REPO_ID,
    repo_type="dataset",
HF_TOKEN=os.environ.get("HF_TOKEN", "")
)
print("  ✅ env.tar.gz uploaded")

# ── Summary ──
print(f"\n{'='*55}")
print(f"  ✅ Build complete!")
print(f"  📁 Dataset: https://huggingface.co/datasets/{REPO_ID}")
print(f"  📊 Sizes:")
print(f"     custom_nodes.tar.gz: {nodes_size:.0f}MB")
print(f"     env.tar.gz: {env_size:.0f}MB")
print(f"     Total: {nodes_size + env_size:.0f}MB")
print(f"{'='*55}\n")
print("  Next: Use main notebook with USE_PREBUILT=True")
