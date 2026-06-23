"""Custom node installation — sequential subprocess cloning."""

from . import config
from .ui import Color, run_cmd


def generate_install_script(comfy_dir):
    """Generate Python script for background node installation."""
    nodes_dir = comfy_dir / "custom_nodes"
    return f'''import subprocess, os
from pathlib import Path

nodes_dir = Path("{nodes_dir}")
ok = 0
fail = 0
total = {len(config.CUSTOM_NODES)}

print("\\n  🧩 Installing custom nodes in background...")
for i, url in enumerate({config.CUSTOM_NODES!r}, 1):
    name = url.split("/")[-1]
    dest = nodes_dir / name
    if not dest.exists():
        print(f"  [{{i:2d}}/{{total}}] ⬇️  {{name}}...", end=" ", flush=True)
        r = subprocess.run(f"git clone --depth=1 {{url}}", shell=True, cwd=str(nodes_dir),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print("✓")
            ok += 1
        else:
            print("✗")
            fail += 1
    else:
        print(f"  [{{i:2d}}/{{total}}] 🔄 {{name}}...", end=" ", flush=True)
        r = subprocess.run("git pull", shell=True, cwd=str(dest),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print("ok")
            ok += 1
        else:
            print("skip")

# Install pip deps
pip_args = []
for p in nodes_dir.iterdir():
    if p.is_dir():
        req = p / "requirements.txt"
        if req.exists():
            pip_args.append(f"-r {{req}}")

if pip_args:
    print(f"\\n  📦 Installing {{len(pip_args)}} node dependencies...", end=" ", flush=True)
    subprocess.run(f"pip install -q {{' '.join(pip_args)}}", shell=True,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓")

print(f"\\n  ✅ Nodes: {{ok}}/{{total}} installed")
print("  NODES_DONE")
'''


def install_nodes_sequential(comfy_dir):
    """Install custom nodes sequentially (for non-background use)."""
    from pathlib import Path

    nodes_dir = Path(comfy_dir) / "custom_nodes"
    nodes_dir.mkdir(exist_ok=True)

    ok = 0
    fail = 0
    total = len(config.CUSTOM_NODES)

    for i, url in enumerate(config.CUSTOM_NODES, 1):
        name = url.split("/")[-1]
        dest = nodes_dir / name
        if not dest.exists():
            print(f"  [{i:2d}/{total}] ⬇️  {name}...", end=" ", flush=True)
            if run_cmd(f"git clone --depth=1 {url}", cwd=nodes_dir, quiet=True):
                print(f"{Color.OKGREEN}✓{Color.ENDC}")
                ok += 1
            else:
                print(f"{Color.FAIL}✗{Color.ENDC}")
                fail += 1
        else:
            print(f"  [{i:2d}/{total}] 🔄 {name}...", end=" ", flush=True)
            if run_cmd("git pull", cwd=dest, quiet=True):
                print(f"{Color.OKBLUE}ok{Color.ENDC}")
                ok += 1
            else:
                print(f"{Color.WARNING}skip{Color.ENDC}")

    # Install pip deps
    pip_args = []
    for node_path in nodes_dir.iterdir():
        if node_path.is_dir():
            req = node_path / "requirements.txt"
            if req.exists():
                pip_args.append(f"-r {req}")

    if pip_args:
        print(f"\n  📦 Installing {len(pip_args)} node dependencies...", end=" ", flush=True)
        run_cmd(f"pip install -q {' '.join(pip_args)}", quiet=True)
        print(f"{Color.OKGREEN}✓{Color.ENDC}")

    print(f"\n  {Color.OKGREEN}✅ Nodes: {ok}/{total} installed{Color.ENDC}")
    return {"ok": ok, "fail": fail, "total": total}
