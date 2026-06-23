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
