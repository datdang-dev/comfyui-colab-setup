# %% [markdown]
# # ComfyUI Environment Setup
# Install all dependencies for ComfyUI + custom nodes.
# Just run this cell — everything is handled automatically.

# %%
#@title 📦 Install Dependencies
import subprocess
from pathlib import Path

SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
SETUP_DIR = Path("/content/comfyui-colab-setup")

# ── Clone setup repo ──
if not SETUP_DIR.exists():
    print("Cloning setup repo...")
    subprocess.run(f"git clone --depth=1 {SETUP_REPO} {SETUP_DIR}", shell=True, check=True)
else:
    print("Setup repo exists, pulling...")
    subprocess.run("git pull", shell=True, cwd=SETUP_DIR)

# ── Clone ComfyUI ──
COMFYUI_DIR = Path("/content/ComfyUI")
if not COMFYUI_DIR.exists():
    print("\nCloning ComfyUI...")
    subprocess.run("git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI", shell=True, check=True)
else:
    print("\nComfyUI already cloned")

# ── Install core deps ──
print("\nInstalling core dependencies...")
subprocess.run("pip install -q -r requirements.txt", shell=True, cwd=str(SETUP_DIR))

# ── Clone + install custom nodes ──
import yaml
config_file = SETUP_DIR / "config.yaml"
if config_file.exists():
    with open(config_file) as f:
        config = yaml.safe_load(f)

    nodes = config.get("nodes", [])
    nodes_dir = COMFYUI_DIR / "custom_nodes"
    nodes_dir.mkdir(exist_ok=True)

    print(f"\nInstalling {len(nodes)} custom nodes...")
    ok = 0
    fail = 0
    for i, node in enumerate(nodes, 1):
        name = node["name"]
        url = node["url"]
        dest = nodes_dir / name

        if not dest.exists():
            print(f"  [{i:2d}/{len(nodes)}] Cloning {name}...", end=" ", flush=True)
            r = subprocess.run(f"git clone --depth=1 {url}", shell=True, cwd=str(nodes_dir),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                print("✓")
                ok += 1
            else:
                print("✗")
                fail += 1
        else:
            print(f"  [{i:2d}/{len(nodes)}] {name} exists, pulling...", end=" ", flush=True)
            subprocess.run("git pull", shell=True, cwd=str(dest),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("ok")
            ok += 1

    # ── Install node deps ──
    print(f"\nInstalling node dependencies...")
    pip_args = []
    for p in nodes_dir.iterdir():
        if p.is_dir():
            req = p / "requirements.txt"
            if req.exists():
                pip_args.append(str(req))

    for i in range(0, len(pip_args), 5):
        batch = pip_args[i:i+5]
        reqs = " ".join([f"-r {r}" for r in batch])
        subprocess.run(f"pip install -q {reqs}", shell=True,
                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    print(f"\n✅ Done: {ok}/{len(nodes)} nodes installed, {fail} failed")
else:
    print("No config.yaml found, skipping node install")
