"""Custom node installation — parallel cloning, pip deps, tar filtering, background script."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Thread

from . import config
from .ui import Color, get_logger, print_header, timer


# ── Tar filtering ──
_TAR_EXCLUDE = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def tar_filter(tarinfo):
    """tarfile filter: skip .git, __pycache__, pytest_cache, node_modules."""
    for excluded in _TAR_EXCLUDE:
        if excluded in tarinfo.name.split("/")[:-1]:
            return None
    return tarinfo


# ── Parallel clone ──
def _clone_one(node, nodes_dir):
    """Clone a single node repo. Returns (name, success, error_msg)."""
    name = node["name"]
    url = node["url"]
    dest = nodes_dir / name

    if dest.exists():
        return name, True, None

    try:
        result = subprocess.run(
            f"git clone --depth=1 {url}",
            shell=True,
            cwd=str(nodes_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return name, True, None
        return name, False, result.stderr.strip().splitlines()[-1] if result.stderr else f"exit {result.returncode}"
    except subprocess.TimeoutExpired:
        return name, False, "clone timed out (>120s)"
    except Exception as e:
        return name, False, str(e)


def install_nodes_parallel(nodes_dir=None, max_workers=None):
    """Install all custom nodes in parallel using ThreadPoolExecutor.

    Returns dict with ok, fail, total counts and a list of failures.
    """
    log = get_logger()
    nodes_dir = Path(nodes_dir or config.CUSTOM_NODES_DIR)
    nodes_dir.mkdir(parents=True, exist_ok=True)
    max_workers = max_workers or config.MAX_NODE_CLONE_WORKERS

    nodes = config.get_custom_nodes()
    total = len(nodes)
    ok = 0
    fail = 0
    failures = []

    log.info(f"Cloning {total} custom nodes ({max_workers} parallel workers)...")

    with timer() as t:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_node = {
                pool.submit(_clone_one, node, nodes_dir): node for node in nodes
            }
            for future in as_completed(future_to_node):
                name, success, error = future.result()
                if success:
                    ok += 1
                    log.info(f"  [{ok + fail:2d}/{total}] {Color.OKGREEN}✓{Color.ENDC} {name}")
                else:
                    fail += 1
                    failures.append({"name": name, "error": error})
                    log.warning(f"  [{ok + fail:2d}/{total}] {Color.FAIL}✗{Color.ENDC} {name}: {error}")

    log.info(f"Nodes cloned: {ok}/{total} ok in {t.elapsed:.0f}s")

    # Install pip dependencies for all cloned nodes
    _install_node_pip_deps(nodes_dir)

    return {"ok": ok, "fail": fail, "total": total, "failures": failures}


def _install_node_pip_deps(nodes_dir):
    """Install pip requirements for all cloned nodes, in batches of 5."""
    log = get_logger()
    nodes_dir = Path(nodes_dir)

    req_files = []
    for p in sorted(nodes_dir.iterdir()):
        if p.is_dir():
            req = p / "requirements.txt"
            if req.exists():
                req_files.append(req)

    if not req_files:
        log.info("  No node requirements.txt found.")
        return

    log.info(f"  Installing {len(req_files)} node dependencies in batches...")

    batch_size = 5
    for i in range(0, len(req_files), batch_size):
        batch = req_files[i : i + batch_size]
        reqs = " ".join([f"-r {r}" for r in batch])
        batch_num = i // batch_size + 1
        total_batches = (len(req_files) + batch_size - 1) // batch_size

        log.info(f"    batch {batch_num}/{total_batches}: {len(batch)} packages")
        result = subprocess.run(
            f"pip install -q {reqs}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            # Log the error but continue — partial deps are better than none
            err_lines = (result.stderr or "").strip().splitlines()[-3:]
            for line in err_lines:
                log.warning(f"      {line}")

    log.info(f"  {Color.OKGREEN}Node dependencies installed.{Color.ENDC}")


# ── Background install (generates a standalone script) ──
def generate_install_script(nodes_dir=None):
    """Generate a standalone Python script for background node installation.

    Used when node install runs in a subprocess while user interacts with model selection.
    """
    nodes = config.get_custom_nodes()
    node_repr = repr([{"name": n["name"], "url": n["url"]} for n in nodes])
    nodes_dir = str(nodes_dir or config.CUSTOM_NODES_DIR)

    return f'''"""Auto-generated node install script — runs in background subprocess."""
import subprocess, sys
from pathlib import Path

NODES_DIR = Path(r"{nodes_dir}")
NODES_DIR.mkdir(parents=True, exist_ok=True)
NODES = {node_repr}
TOTAL = len(NODES)

print("\\n  Installing custom nodes in background...")
ok, fail = 0, 0

for i, node in enumerate(NODES, 1):
    name, url = node["name"], node["url"]
    dest = NODES_DIR / name
    if dest.exists():
        ok += 1
        print(f"  [{{i:2d}}/{{TOTAL}}] {{name}}... exists")
        continue
    try:
        r = subprocess.run(
            f"git clone --depth=1 {{url}}",
            shell=True, cwd=str(NODES_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=120,
        )
        if r.returncode == 0:
            ok += 1
            print(f"  [{{i:2d}}/{{TOTAL}}] ok  {{name}}", flush=True)
        else:
            fail += 1
            err = r.stderr.strip().splitlines()[-1] if r.stderr else "unknown"
            print(f"  [{{i:2d}}/{{TOTAL}}] FAIL {{name}}: {{err}}", flush=True)
    except Exception as e:
        fail += 1
        print(f"  [{{i:2d}}/{{TOTAL}}] FAIL {{name}}: {{e}}", flush=True)

# pip deps
req_files = []
for p in sorted(NODES_DIR.iterdir()):
    if p.is_dir() and (p / "requirements.txt").exists():
        req_files.append(p / "requirements.txt")

if req_files:
    print(f"\\n  Installing {{len(req_files)}} node deps...")
    for i in range(0, len(req_files), 5):
        batch = req_files[i:i+5]
        reqs = " ".join([f"-r {{r}}" for r in batch])
        subprocess.run(
            f"pip install -q {{reqs}}", shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
        )
    print("  Node deps done.")

print(f"\\n  NODES_DONE: {{ok}}/{{TOTAL}} ok, {{fail}} failed")
'''


def start_background_install(comfy_dir):
    """Launch node install in a background subprocess and stream output via a thread.

    Returns the Popen object.
    """
    log = get_logger()
    script = generate_install_script(comfy_dir / "custom_nodes")
    script_path = "/tmp/_install_nodes_bg.py"
    with open(script_path, "w") as f:
        f.write(script)

    log.info(f"Starting background node install (PID will be logged below)...")

    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log.info(f"  PID: {proc.pid}")

    # Stream output in a daemon thread so it appears live in the terminal
    def _stream_output():
        for line in proc.stdout:
            print(line.rstrip(), flush=True)

    Thread(target=_stream_output, daemon=True).start()
    return proc
