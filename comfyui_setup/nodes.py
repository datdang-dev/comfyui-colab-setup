"""Custom node installation — parallel cloning, pip deps, tar filtering, background script."""

import re
import subprocess
import sys
import tempfile
from collections import defaultdict
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


def _parse_requirement_line(line):
    """Parse a single requirement line. Returns (package_name_lower, raw_line) or None."""
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    # Extract package name (before any version specifier)
    match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)", line)
    if match:
        return match.group(1).lower().replace("-", "_"), line
    return None


def _collect_and_merge_requirements(req_files):
    """Collect all requirements, merge version constraints per package.

    Returns:
        merged_lines: list of merged requirement lines
        conflicts: list of (package, [(node_name, spec), ...]) for packages with multiple constraints
        all_lines: dict of {package_name: [(node_dir_name, raw_line), ...]}
    """
    # package_name -> [(node_dir_name, raw_line, version_spec)]
    all_reqs = defaultdict(list)
    passthrough_lines = []  # lines we can't parse (flags, comments, etc.)

    for req_file in req_files:
        node_name = req_file.parent.name
        with open(req_file, encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                parsed = _parse_requirement_line(raw_line)
                if parsed is None:
                    # Keep flags like --extra-index-url, --find-links
                    stripped = raw_line.strip()
                    if stripped.startswith("-"):
                        passthrough_lines.append(stripped)
                    continue
                pkg_name, raw_req = parsed
                all_reqs[pkg_name].append((node_name, raw_req))

    # Merge: for each package, combine all version specs
    merged_lines = []
    conflicts = []

    for pkg_name, entries in sorted(all_reqs.items()):
        if len(entries) == 1:
            # Only one node needs this package — use as-is
            merged_lines.append(entries[0][1])
        else:
            # Multiple nodes need this package — merge version specs
            specs = []
            raw_lines = []
            for node_name, raw_req in entries:
                # Extract version spec part (e.g., >=1.4, <2.0)
                match = re.match(r"^[A-Za-z0-9_][A-Za-z0-9._-]*(.*)", raw_req)
                spec = match.group(1).strip() if match else ""
                if spec:
                    specs.append((node_name, spec))
                raw_lines.append(raw_req)

            if len(set(s for _, s in specs)) > 1:
                # Different version specs — record as conflict
                conflicts.append((pkg_name, specs))

            # Build merged line: package>=spec1,>=spec2 (pip handles this)
            display_name = entries[0][1].split(">=")[0].split("<=")[0].split("==")[0].split("!=")[0].split(">")[0].split("<")[0].strip()
            if specs:
                combined = ",".join(s for _, s in specs)
                merged_lines.append(f"{display_name}{combined}")
            else:
                merged_lines.append(entries[0][1])

    # Deduplicate passthrough lines
    seen_flags = set()
    unique_flags = []
    for flag in passthrough_lines:
        if flag not in seen_flags:
            seen_flags.add(flag)
            unique_flags.append(flag)

    return unique_flags + merged_lines, conflicts, all_reqs


def _install_node_pip_deps(nodes_dir):
    """Install pip requirements for all cloned nodes.

    Strategy:
    1. Collect all requirements.txt files
    2. Parse and merge version constraints per package
    3. Detect and report conflicts
    4. Write merged requirements to temp file
    5. Single pip install --no-cache-dir call
    """
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

    # Collect and merge
    merged_lines, conflicts, all_reqs = _collect_and_merge_requirements(req_files)

    total_pkgs = len(all_reqs)
    log.info(f"  Collected {total_pkgs} unique packages from {len(req_files)} nodes")

    # Report conflicts (informational — pip will resolve)
    if conflicts:
        log.info(f"  {len(conflicts)} packages have multiple version constraints:")
        for pkg_name, specs in conflicts[:10]:  # show first 10
            spec_str = ", ".join(f"{node} wants {s}" for node, s in specs)
            log.info(f"    {pkg_name}: {spec_str}")
        if len(conflicts) > 10:
            log.info(f"    ... and {len(conflicts) - 10} more")

    # Write merged requirements to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="merged_req_") as tmp:
        tmp.write("\n".join(merged_lines) + "\n")
        tmp_path = tmp.name

    log.info(f"  Installing merged requirements (single pip call)...")

    result = subprocess.run(
        f"pip install --no-cache-dir -q -r {tmp_path}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        err_lines = (result.stderr or "").strip().splitlines()[-10:]
        for line in err_lines:
            log.warning(f"    {line}")
        log.warning(f"  {Color.FAIL}pip install failed — see errors above{Color.ENDC}")
    else:
        log.info(f"  {Color.OKGREEN}Node dependencies installed ({total_pkgs} packages).{Color.ENDC}")

    # Cleanup temp file
    try:
        Path(tmp_path).unlink()
    except OSError:
        pass


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

# pip deps — single pip call with all requirements
req_files = []
for p in sorted(NODES_DIR.iterdir()):
    if p.is_dir() and (p / "requirements.txt").exists():
        req_files.append(p / "requirements.txt")

if req_files:
    reqs = " ".join([f"-r {{r}}" for r in req_files])
    print(f"\\n  Installing deps from {{len(req_files)}} nodes (single pip call)...")
    subprocess.run(
        f"pip install --no-cache-dir -q {{reqs}}", shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900,
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
