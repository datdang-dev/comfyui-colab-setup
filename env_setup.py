# %% [markdown]
# # ComfyUI Environment Builder
# Build pre-built conda environment for fast Colab setup.

# %%
#@title Step 1 - Create Conda Environment
import subprocess
from pathlib import Path

SETUP_REPO = "https://github.com/datdang-dev/comfyui-colab-setup.git"
SETUP_DIR = Path("/content/comfyui-colab-setup")

if not SETUP_DIR.exists():
    print("Cloning setup repo...")
    subprocess.run(f"git clone --depth=1 {SETUP_REPO} {SETUP_DIR}", shell=True, check=True)
else:
    print("Setup repo exists, pulling...")
    subprocess.run("git pull", shell=True, cwd=SETUP_DIR)

# conda is pre-installed in Colab
print("Using pre-installed conda...")

ENV_NAME = "comfyui"
ENV_YML = SETUP_DIR / "environment.yml"

subprocess.run(f"conda env create -f {ENV_YML} -y", shell=True, check=True)

CUSTOM_NODES_DIR = SETUP_DIR / "custom_nodes"
if CUSTOM_NODES_DIR.exists():
    pip_args = []
    for node_path in CUSTOM_NODES_DIR.iterdir():
        if node_path.is_dir():
            req = node_path / "requirements.txt"
            if req.exists():
                pip_args.append(str(req))
    for i in range(0, len(pip_args), 5):
        batch = pip_args[i:i+5]
        reqs = " ".join([f"-r {r}" for r in batch])
        subprocess.run(f"conda run -n {ENV_NAME} pip install -q {reqs}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

subprocess.run("conda install -n base conda-pack -y -c conda-forge", shell=True, check=True)
print(f"Environment ready!")

# %% [markdown]
# # Step 2: Package Environment

# %%
#@title Step 2 - Package Environment
import subprocess
from pathlib import Path

ENV_NAME = "comfyui"
PACK_FILE = Path("/content/comfyui-env.tar.gz")

subprocess.run(f"conda-pack -n {ENV_NAME} -o {PACK_FILE} --force", shell=True, check=True)
size_mb = PACK_FILE.stat().st_size / (1024 * 1024)
print(f"Packaged: {PACK_FILE} ({size_mb:.0f}MB)")

# %% [markdown]
# # Step 3: Upload to HF

# %%
#@title Step 3 - Upload to HF
import getpass
from pathlib import Path
from huggingface_hub import HfApi

HF_TOKEN = getpass.getpass("HF Token: ")
REPO_ID = "datsss/comfyui-env"
PACK_FILE = Path("/content/comfyui-env.tar.gz")

if not PACK_FILE.exists():
    print("File not found. Run Step 2 first.")
else:
    api = HfApi()
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", token=HF_TOKEN, exist_ok=True)
    print(f"Uploading {PACK_FILE.stat().st_size/(1024*1024):.0f}MB to {REPO_ID}...")
    api.upload_file(
        path_or_fileobj=str(PACK_FILE),
        path_in_repo="comfyui-env.tar.gz",
        repo_id=REPO_ID,
        repo_type="dataset",
        token=HF_TOKEN,
    )
    print("Done!")
    print(f"Dataset: https://huggingface.co/datasets/{REPO_ID}")
