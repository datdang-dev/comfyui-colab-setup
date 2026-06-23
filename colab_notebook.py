# %% [markdown]
# <div style="padding: 24px; border-radius: 16px; background: linear-gradient(135deg, #1E1B4B 0%, #311042 50%, #4C1D95 100%); color: white; font-family: Outfit, -apple-system, sans-serif; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
#     <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">ComfyUI Colab Setup</h1>
#     <p style="margin: 8px 0 0 0; font-size: 15px; color: #C4B5FD;">One-click setup for ComfyUI + custom nodes + model download</p>
# </div>

# %% [markdown]
# ## Cell 1 - Setup

# %%
#@title Parameters
USE_PREBUILT = True  #@param {type:"boolean"}
REPO_ID = "datsss/my-dataset"  #@param {type:"string"}
REPO_TYPE = "dataset"  #@param ["dataset", "model"]
MAX_PARALLEL = 8  #@param {type:"integer"}

import subprocess, os, sys

SETUP_REPO = "https://github.com/datsss/comfyui-setup.git"
SETUP_DIR = "/content/comfyui-setup"

if not os.path.exists(SETUP_DIR):
    print("Cloning setup repo...")
    subprocess.run(f"git clone --depth=1 {SETUP_REPO} {SETUP_DIR}", shell=True, check=True)
else:
    subprocess.run("git pull", shell=True, cwd=SETUP_DIR)

if not os.path.exists("/content/ComfyUI"):
    print("Cloning ComfyUI...")
    subprocess.run("git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI", shell=True, check=True)

cmd = f"python {SETUP_DIR}/install.py --repo-id={REPO_ID} --repo-type={REPO_TYPE} --max-parallel={MAX_PARALLEL}"
if USE_PREBUILT:
    cmd += " --use-prebuilt"
subprocess.run(cmd, shell=True)

# %% [markdown]
# ## Cell 2 - Launch

# %%
#@title Launch
import subprocess, time, urllib.request, re

proc = subprocess.Popen("python main.py --listen 0.0.0.0 --port 8188", shell=True, cwd="/content/ComfyUI", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for i in range(30):
    try:
        urllib.request.urlopen("http://localhost:8188/system_stats", timeout=2)
        break
    except:
        time.sleep(1)

tunnel = subprocess.Popen("cloudflared tunnel --url http://localhost:8188", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in tunnel.stdout:
    match = re.search(r"https://[a-z0-9-]+.trycloudflare.com", line)
    if match:
        print(f"OPEN: {match.group(0)}")
        break
