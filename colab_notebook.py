# %% [markdown]
# # ComfyUI Colab Setup
# One-click setup for ComfyUI + custom nodes + model download.

# %% [markdown]
# ## Cell 1 — Setup
# Clone ComfyUI, install deps, select & download models.

# %%
#@title ⚙️ Parameters
USE_PREBUILT = True  #@param {type:"boolean"}
REPO_ID = "datsss/my-dataset"  #@param {type:"string"}
REPO_TYPE = "dataset"  #@param ["dataset", "model"]
MAX_PARALLEL = 8  #@param {type:"integer"}

import subprocess, os, sys
from pathlib import Path

SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
SETUP_DIR = Path("/content/comfyui-colab-setup")

# ── Clone setup repo ──
if not SETUP_DIR.exists():
    print("Cloning setup repo...")
    subprocess.run(f"git clone --depth=1 {SETUP_REPO} {SETUP_DIR}", shell=True, check=True)
else:
    subprocess.run("git pull", shell=True, cwd=SETUP_DIR)

# ── Clone ComfyUI ──
if not Path("/content/ComfyUI").exists():
    print("Cloning ComfyUI...")
    subprocess.run("git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI", shell=True, check=True)

# ── Run install ──
cmd = f"python {SETUP_DIR}/install.py --repo-id={REPO_ID} --repo-type={REPO_TYPE} --max-parallel={MAX_PARALLEL}"
if USE_PREBUILT:
    cmd += " --use-prebuilt"
subprocess.run(cmd, shell=True)

# %% [markdown]
# ## Cell 2 — Launch
# Start ComfyUI server + Cloudflare tunnel.

# %%
#@title 🚀 Launch
import subprocess, time, urllib.request, re

proc = subprocess.Popen("python main.py --listen 0.0.0.0 --port 8188", shell=True, cwd="/content/ComfyUI",
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"ComfyUI PID: {proc.pid}")

for i in range(30):
    try:
        urllib.request.urlopen("http://localhost:8188/system_stats", timeout=2)
        break
    except:
        time.sleep(1)

tunnel = subprocess.Popen("cloudflared tunnel --url http://localhost:8188", shell=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in tunnel.stdout:
    match = re.search(r"https://[a-z0-9-]+.trycloudflare.com", line)
    if match:
        print(f"\nOPEN: {match.group(0)}")
        break
