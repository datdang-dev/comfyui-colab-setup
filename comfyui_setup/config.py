"""Configuration — constants, config.yaml loader, dynamic paths."""

import os
import site
import subprocess
from pathlib import Path

# ── Paths ──
WORKSPACE = Path("/content")
COMFYUI_DIR = WORKSPACE / "ComfyUI"
CUSTOM_NODES_DIR = COMFYUI_DIR / "custom_nodes"
CONFIG_YAML = Path(__file__).parent.parent / "config.yaml"
LOG_FILE = WORKSPACE / "comfyui_setup.log"
DOWNLOAD_LIST_FILE = str(WORKSPACE / "download_list.json")

# ── ComfyUI ──
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"

# ── HF Dataset ──
DEFAULT_REPO_ID = "datsss/my-dataset"
DEFAULT_REPO_TYPE = "dataset"
DEFAULT_ENV_REPO = "datsss/comfyui-env"

# ── Model Categories ──
CATEGORIES = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "embedding": "embeddings",
    "ipadapters": "ipadapter",
    "clip_vision": "clip_vision",
    "upscalers": "upscale_models",
    "text_encoders": "text_encoders",
    "vae": "vae",
    "diffusion_models": "diffusion_models",
}

# ── Download ──
MAX_DOWNLOAD_PARALLEL = 8
MAX_NODE_CLONE_WORKERS = 6

# ── Fallback node list (used if config.yaml not found) ──
_FALLBACK_NODES = [
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


def load_config_yaml(config_path=None):
    """Load and return the parsed config.yaml dict, or {} on failure."""
    path = Path(config_path) if config_path else CONFIG_YAML
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_custom_nodes(config_path=None):
    """Return list of node dicts [{name, url}] from config.yaml, or fallback list."""
    cfg = load_config_yaml(config_path)
    nodes_raw = cfg.get("nodes", [])
    if not nodes_raw:
        return [{"name": url.split("/")[-1], "url": url} for url in _FALLBACK_NODES]

    result = []
    for node in nodes_raw:
        if isinstance(node, dict):
            result.append({"name": node.get("name", ""), "url": node.get("url", "")})
        elif isinstance(node, str):
            result.append({"name": node.split("/")[-1], "url": node})
    return result


def get_comfyui_repo(config_path=None):
    """Return ComfyUI repo URL from config.yaml or fallback."""
    cfg = load_config_yaml(config_path)
    comfyui_cfg = cfg.get("comfyui", {})
    return comfyui_cfg.get("repo", COMFYUI_REPO)


def get_site_packages():
    """Detect Python site-packages directory dynamically.

    Tries site.getsitepackages() first, falls back to a subprocess probe.
    """
    try:
        return Path(site.getsitepackages()[0])
    except Exception:
        pass
    try:
        output = subprocess.check_output(
            "python -c 'import site; print(site.getsitepackages()[0])'",
            shell=True,
            text=True,
        ).strip()
        return Path(output)
    except Exception as e:
        raise RuntimeError(f"Cannot determine site-packages: {e}")
