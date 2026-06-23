# %% [markdown]
# <div style="padding: 24px; border-radius: 16px; background: linear-gradient(135deg, #1E1B4B 0%, #311042 50%, #4C1D95 100%); color: white; font-family: 'Outfit', -apple-system, sans-serif; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
#     <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">🎨 ComfyUI Colab</h1>
#     <p style="margin: 8px 0 0 0; font-size: 15px; color: #C4B5FD;">One-click setup with model management</p>
#     <p style="margin: 4px 0 0 0; font-size: 13px; color: #9CA3AF;">Version 4.0.0 • Modular Python package</p>
# </div>

# %% [markdown]
# <div style="border-left: 5px solid #6366F1; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">1. Setup</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Install comfyui-setup package and run full flow.</p>
# </div>

# %%
#@title 🔧 Setup & Run
HF_TOKEN = ""  #@param {type:"string"}
REPO_ID = "datsss/my-dataset" #@param {type:"string"}
REPO_TYPE = "dataset" #@param ["dataset", "model"]
MAX_PARALLEL = 8 #@param {type:"slider", min:1, max:32, step:1}

import os
import sys

# Install comfyui-setup from local or GitHub
SETUP_REPO = "https://github.com/datsss/comfyui-setup.git" #@param {type:"string"}
SETUP_DIR = "/content/comfyui-setup"

if not os.path.exists(SETUP_DIR):
    !git clone --depth=1 $SETUP_REPO $SETUP_DIR

if SETUP_DIR not in sys.path:
    sys.path.insert(0, SETUP_DIR)

# Run full setup
from comfyui_setup.main import run
run(
    hf_token=HF_TOKEN,
    repo_id=REPO_ID,
    repo_type=REPO_TYPE,
    max_parallel=MAX_PARALLEL,
)

# %% [markdown]
# <div style="border-left: 5px solid #10B981; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">2. Launch</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Start ComfyUI server and open tunnel.</p>
# </div>

# %%
#@title 🚀 Cloudflare Tunnel
EXTRA_ARGS = "--dont-print-server --force-fp16" #@param {type:"string"}

from comfyui_setup.tunnel import start_cloudflare
from comfyui_setup.ui import start_comfyui

start_comfyui(extra_args=EXTRA_ARGS)
start_cloudflare()
