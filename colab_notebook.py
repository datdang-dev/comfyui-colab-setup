# %% [markdown]
# # ComfyUI Colab
# Downloads pre-built environment from HuggingFace (~2min).

# %% [markdown]
# ## Cell 1 — Setup

# %%
#@title ⚙️ Parameters
HF_TOKEN = ""  #@param {type:"string"}
REPO_ID = "datsss/my-dataset"  #@param {type:"string"}
REPO_TYPE = "dataset"  #@param ["dataset", "model"]
MAX_PARALLEL = 8  #@param {type:"integer"}

import subprocess, os
from pathlib import Path

# ── Load pre-built environment ──
ENV_REPO = "datsss/comfyui-env"
WORKSPACE = Path("/content")

print("Downloading pre-built environment from HuggingFace...")
subprocess.run("pip install -q huggingface_hub hf_transfer", shell=True)

from huggingface_hub import hf_hub_download

# Download custom_nodes
print("  Downloading custom_nodes.tar.gz...")
nodes_archive = hf_hub_download(repo_id=ENV_REPO, filename="custom_nodes.tar.gz",
                                repo_type="dataset", token=HF_TOKEN or None)
print("  Extracting custom_nodes...")
subprocess.run(f"tar -xzf {nodes_archive} -C {WORKSPACE}", shell=True, check=True)

# Download env
print("  Downloading comfyui-env.tar.gz...")
env_archive = hf_hub_download(repo_id=ENV_REPO, filename="comfyui-env.tar.gz",
                              repo_type="dataset", token=HF_TOKEN or None)
print("  Extracting environment...")
subprocess.run(f"tar -xzf {env_archive} -C {WORKSPACE}", shell=True, check=True)

print("✅ Environment ready!")

# ── Run install script (for models) ──
SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
SETUP_DIR = WORKSPACE / "comfyui-colab-setup"

if not SETUP_DIR.exists():
    subprocess.run(f"git clone --depth=1 {SETUP_REPO} {SETUP_DIR}", shell=True, check=True)

cmd = f"python {SETUP_DIR}/install.py --repo-id={REPO_ID} --repo-type={REPO_TYPE} --max-parallel={MAX_PARALLEL} --skip-nodes"
if HF_TOKEN:
    cmd += f" --hf-token={HF_TOKEN}"
subprocess.run(cmd, shell=True)

# %% [markdown]
# ## Cell 2 — Launch

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
