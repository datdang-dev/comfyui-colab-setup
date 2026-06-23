"""UI utilities — Color class, run_cmd, helpers."""

import subprocess


class Color:
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def run_cmd(command, cwd=None, quiet=False, ignore_errors=False):
    """Run shell command. Returns True on success."""
    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=cwd,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
        return True
    except subprocess.CalledProcessError:
        if not ignore_errors:
            raise
        return False


def check_server_ready(port, timeout=120):
    """Wait for ComfyUI server to be ready."""
    import socket
    import time

    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=1)
            sock.close()
            print(f"{Color.OKGREEN}🟢 ComfyUI ready on port {port}{Color.ENDC}")
            return True
        except Exception:
            time.sleep(0.5)

    print(f"{Color.FAIL}❌ Server did not start within {timeout}s{Color.ENDC}")
    return False


def start_comfyui(extra_args="", port=8188):
    """Start ComfyUI server."""
    import os
    from pathlib import Path

    workspace = Path(os.environ.get("WORKSPACE", "/content"))
    comfy_dir = workspace / "ComfyUI"

    cmd = f"python {comfy_dir}/main.py --listen 0.0.0.0 --port {port} {extra_args}"
    print(f"  🚀 Starting ComfyUI...")
    print(f"  $ {cmd}\n")

    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(comfy_dir),
    )

    check_server_ready(port)
    return proc
