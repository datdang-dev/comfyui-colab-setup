# ComfyUI Colab Setup

One-click ComfyUI environment for Google Colab. Two workflows:

1. **Build** (once) — install everything, pack into tarballs, upload to HuggingFace
2. **Run** (every session) — download pre-built env in ~2min, select models, generate

## Quick Start

### Build environment (run once)
```bash
# On Colab terminal:
git clone https://github.com/datdang-dev/comfyui-colab-setup
cd comfyui-colab-setup
python setup_env.py --hf-token=YOUR_HF_TOKEN
```

### Run session
```bash
# On Colab terminal:
git clone https://github.com/datdang-dev/comfyui-colab-setup
cd comfyui-colab-setup
python install.py --hf-token=YOUR_HF_TOKEN --use-prebuilt
```

## Project Structure

```
comfyui-colab-setup/
├── setup_env.py              # Build script — pack env, upload to HF
├── install.py                # Run script — thin CLI wrapper
├── config.yaml               # Node list, ComfyUI repo URL (edit this to customize)
├── requirements.txt          # Core pip dependencies
├── colab_notebook.ipynb      # Keep-alive notebook for Colab
├── colab_notebook.py         # Keep-alive script (alternative to notebook)
└── comfyui_setup/            # Core Python package
    ├── config.py             # Config loader, paths, constants
    ├── core.py               # Clone ComfyUI, load prebuilt env
    ├── nodes.py              # Parallel node cloning, tar filtering, background install
    ├── models.py             # Model downloading (hf_transfer, parallel)
    ├── select.py             # Interactive per-category model selection
    ├── main.py               # Orchestrator — full setup flow
    ├── tunnel.py             # Cloudflare / LocalTunnel / Ngrok launchers
    └── ui.py                 # Logging (timestamps + file), Color, run_cmd, helpers
```

## Build Script (`setup_env.py`)

Packages the entire Colab environment into two tarballs and uploads to HF:
- `custom_nodes.tar.gz` — all 16 custom nodes
- `comfyui-env.tar.gz` — Python site-packages + ComfyUI core

**Optimizations:**
- Uses `pigz` (parallel gzip) for 2-4x faster compression on multi-core instances
- Excludes `.git` / `__pycache__` from archives to reduce size
- Parallel upload of both tarballs
- Timestamped logging to console + `/content/build.log`
- Reads node list from `config.yaml` (not hardcoded)

## Run Script (`install.py`)

Two modes:
- `--use-prebuilt` — downloads pre-built env from HF (fast, ~2min)
- Without flag — fresh install from scratch

Full flow:
1. Clone ComfyUI (or load prebuilt)
2. Install custom nodes in background (parallel, streamed to terminal)
3. Interactive model selection (while nodes install)
4. Download models (hf_transfer, 8 parallel)
5. Wait for node install to finish

## Configuration

Edit `config.yaml` to add/remove/pin custom nodes:
```yaml
nodes:
  - name: "ComfyUI-Manager"
    url: "https://github.com/ltdrdata/ComfyUI-Manager.git"
    branch: "main"
    required: true
```

## Logging

All scripts log to both console (colored, compact timestamps) and a file:
- Build: `/content/build.log`
- Run: `/content/comfyui_setup.log`

Output survives terminal disconnects — check the log file if you lose connection.
# ComfyUI Colab Setup

Modular Python package for one-click ComfyUI Colab setup.

## Usage

### Colab Notebook (recommended)
1. Open `colab_notebook.ipynb` in Colab
2. Set parameters (HF_TOKEN, REPO_ID, MAX_PARALLEL)
3. Run all cells

### Programmatic
```python
from comfyui_setup.main import run
run(hf_token="hf_xxx", repo_id="datsss/my-dataset", max_parallel=8)
```

## Structure

```
comfyui_setup/
├── config.py       # Constants, URLs, defaults
├── core.py         # Clone ComfyUI, install deps
├── nodes.py        # Custom node installation
├── models.py       # Download models (hf_transfer)
├── select.py       # Interactive model selection
├── tunnel.py       # Cloudflare/LocalTunnel/Ngrok
├── ui.py           # Color class, run_cmd, helpers
└── main.py         # Entry point
```

## Flow

1. **Setup** — Clone ComfyUI core, start background node install
2. **Select** — Per-category interactive model selection
3. **Download** — Parallel model download with hf_transfer
4. **Launch** — Start ComfyUI + tunnel

## Custom Nodes

Default list in `config.py`:

- ComfyUI-Manager
- IPAdapter Plus
- ControlNet Aux
- Impact Pack
- Custom Scripts
- rgthree-comfy
- KJNodes
- Efficiency Nodes
- Essentials
- Image Saver
- Impact Subpack
- Mnemic Nodes
- LLM Toolkit
- Resolution Selector
- Python Extension
- UltimateSDUpscale
