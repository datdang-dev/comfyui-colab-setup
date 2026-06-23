# %% [markdown]
# <div style="padding: 24px; border-radius: 16px; background: linear-gradient(135deg, #1E1B4B 0%, #311042 50%, #4C1D95 100%); color: white; font-family: 'Outfit', -apple-system, sans-serif; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
#     <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">🎨 ComfyUI Colab</h1>
#     <p style="margin: 8px 0 0 0; font-size: 15px; color: #C4B5FD;">One-click setup with model management</p>
#     <p style="margin: 4px 0 0 0; font-size: 13px; color: #9CA3AF;">Version 4.2.0 • Pre-built environment support</p>
# </div>

# %% [markdown]
# <div style="border-left: 5px solid #6366F1; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">1. Setup</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Clone ComfyUI and run install script.</p>
# </div>

# %%
#@title 🔧 Setup & Run
HF_TOKEN = ""  #@param {type:"string"}
REPO_ID = "datsss/my-dataset" #@param {type:"string"}
REPO_TYPE = "dataset" #@param ["dataset", "model"]
MAX_PARALLEL = 8 #@param {type:"slider", min:1, max:32, step:1}
USE_PREBUILT = True #@param {type:"boolean"}

import os

# Clone install script from GitHub
SETUP_REPO = "https://github.com/datsss/comfyui-setup.git" #@param {type:"string"}
SETUP_DIR = "/content/comfyui-setup"

if not os.path.exists(SETUP_DIR):
    !git clone --depth=1 $SETUP_REPO $SETUP_DIR

# Clone ComfyUI repo
COMFYUI_DIR = "/content/ComfyUI"
if not os.path.exists(COMFYUI_DIR):
    !git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git $COMFYUI_DIR

# Run install script
if USE_PREBUILT:
    !python $SETUP_DIR/install.py --hf-token=HF_TOKEN --repo-id=$REPO_ID --repo-type=$REPO_TYPE --max-parallel=$MAX_PARALLEL --workspace=/content --use-prebuilt
else:
    !python $SETUP_DIR/install.py --hf-token=HF_TOKEN --repo-id=$REPO_ID --repo-type=$REPO_TYPE --max-parallel=$MAX_PARALLEL --workspace=/content

# %% [markdown]
# <div style="border-left: 5px solid #10B981; padding: 4px 16px; font-family: 'Inter', sans-serif; margin: 24px 0 16px 0;">
#     <h2 style="color: #1F2937; margin: 0; font-size: 20px; font-weight: 600;">2. Launch</h2>
#     <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0 0;">Start ComfyUI server and open tunnel.</p>
# </div>

# %%
#@title 🚀 Cloudflare Tunnel
EXTRA_ARGS = "--dont-print-server --force-fp16" #@param {type:"string"}

import subprocess
import threading
import re

PORT = 8188

# Start ComfyUI in background
cmd = f"python /content/ComfyUI/main.py --listen 0.0.0.0 --port {PORT} {EXTRA_ARGS}"
proc = subprocess.Popen(cmd, shell=True, cwd="/content/ComfyUI")

# Wait for server ready
import socket, time
start = time.time()
while time.time() - start < 120:
    try:
        sock = socket.create_connection(("127.0.0.1", PORT), timeout=1)
        sock.close()
        print(f"🟢 ComfyUI ready on port {PORT}")
        break
    except:
        time.sleep(0.5)

# Install and start cloudflared
!curl -sL --output /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i /tmp/cf.deb > /dev/null 2>&1

def run_tunnel():
    import urllib.request
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--protocol", "http2", "--url", f"http://127.0.0.1:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in proc.stdout:
        print(line.rstrip())
        match = re.search(r"(https://[a-zA-Z0-9.-]+\.trycloudflare\.com)", line)
        if match:
            print(f"\n🌐 URL: {match.group(1)}\n")
            break

threading.Thread(target=run_tunnel, daemon=True).start()
