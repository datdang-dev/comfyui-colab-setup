# %% [markdown]
# # ComfyUI Environment Builder
# **Run this ONCE** to build and upload pre-built environment to HuggingFace.
# After that, main notebook downloads it in ~2 minutes instead of installing from scratch.

# %%
#@title Step 1 - Clone & Install Everything
import subprocess
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
COMFYUI_DIR = Path("/content/ComfyUI")
if not COMFYUI_DIR.exists():
    print("\nCloning ComfyUI...")
    subprocess.run("git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI", shell=True, check=True)

# ── Install core deps ──
print("\nInstalling core dependencies...")
subprocess.run("pip install -q -r requirements.txt", shell=True, cwd=str(SETUP_DIR))

# ── Clone + install custom nodes ──
import yaml
config_file = SETUP_DIR / "config.yaml"
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
        print(f"  [{i:2d}/{len(nodes)}] {name}...", end=" ", flush=True)
        r = subprocess.run(f"git clone --depth=1 {url}", shell=True, cwd=str(nodes_dir),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print("✓")
            ok += 1
        else:
            print("✗")
            fail += 1

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

print(f"\n✅ Environment ready! {ok}/{len(nodes)} nodes installed")

# %% [markdown]
# # Step 2: Package Environment

# %%
#@title Step 2 - Package Environment
import subprocess, tarfile, os
from pathlib import Path

COMFYUI_DIR = Path("/content/ComfyUI")
PACK_FILE = Path("/content/comfyui-env.tar.gz")

# ── Package custom_nodes ──
print("Packaging custom_nodes...")
nodes_tar = Path("/content/custom_nodes.tar.gz")
with tarfile.open(nodes_tar, "w:gz") as tar:
    nodes_dir = COMFYUI_DIR / "custom_nodes"
    for node_dir in nodes_dir.iterdir():
        if node_dir.is_dir():
            tar.add(node_dir, arcname=f"ComfyUI/custom_nodes/{node_dir.name}")
print(f"  custom_nodes.tar.gz: {nodes_tar.stat().st_size/(1024*1024):.0f}MB")

# ── Package Python site-packages ──
print("\nPackaging Python environment...")
site_packages = Path(subprocess.check_output(
    "python -c 'import site; print(site.getsitepackages()[0])'",
    shell=True, text=True).strip())
print(f"  Site packages: {site_packages}")

with tarfile.open(PACK_FILE, "w:gz") as tar:
    # Add site-packages
    tar.add(site_packages, arcname="site-packages")
    # Add ComfyUI core (minus custom_nodes)
    for item in COMFYUI_DIR.iterdir():
        if item.name == "custom_nodes":
            continue
        tar.add(item, arcname=f"ComfyUI/{item.name}")

print(f"  comfyui-env.tar.gz: {PACK_FILE.stat().st_size/(1024*1024):.0f}MB")
print("\n✅ Packaging complete!")

# %% [markdown]
# # Step 3: Upload to HuggingFace

# %%
#@title Step 3 - Upload to HF
import getpass
from pathlib import Path
from huggingface_hub import HfApi

HF_TOKEN = getpass.getpass("HF Token: ")
REPO_ID = "datsss/comfyui-env"
PACK_FILE = Path("/content/comfyui-env.tar.gz")
NODES_FILE = Path("/content/custom_nodes.tar.gz")

if not PACK_FILE.exists():
    print("File not found. Run Step 2 first.")
else:
    api = HfApi()
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", token=HF_TOKEN, exist_ok=True)

    print(f"Uploading comfyui-env.tar.gz ({PACK_FILE.stat().st_size/(1024*1024):.0f}MB)...")
    api.upload_file(
        path_or_fileobj=str(PACK_FILE),
        path_in_repo="comfyui-env.tar.gz",
        repo_id=REPO_ID,
        repo_type="dataset",
        token=HF_TOKEN,
    )

    print(f"Uploading custom_nodes.tar.gz ({NODES_FILE.stat().st_size/(1024*1024):.0f}MB)...")
    api.upload_file(
        path_or_fileobj=str(NODES_FILE),
        path_in_repo="custom_nodes.tar.gz",
        repo_id=REPO_ID,
        repo_type="dataset",
        token=HF_TOKEN,
    )

    print("\n✅ Done!")
    print(f"Dataset: https://huggingface.co/datasets/{REPO_ID}")
