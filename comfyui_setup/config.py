"""Default configuration for ComfyUI Colab Setup."""

# ── ComfyUI ──
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
WORKSPACE = "/content"

# ── Custom Nodes ──
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

# ── HF Dataset ──
DEFAULT_REPO_ID = "datsss/my-dataset"
DEFAULT_REPO_TYPE = "dataset"

# ── Model Categories ──
CATEGORIES = {
    "checkpoint":       "checkpoints",
    "lora":             "loras",
    "embedding":        "embeddings",
    "ipadapters":       "ipadapter",
    "clip_vision":      "clip_vision",
    "upscalers":        "upscale_models",
    "text_encoders":    "text_encoders",
    "vae":              "vae",
    "diffusion_models": "diffusion_models",
}

# ── Download ──
MAX_DOWNLOAD_PARALLEL = 8
DOWNLOAD_LIST_FILE = "/content/download_list.json"
