"""UI utilities — logging with timestamps, file output, colored console, run_cmd, server helpers."""

import logging
import os
import subprocess
import time
from pathlib import Path


# ── ANSI Colors ──
class Color:
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


# ── Logging ──
_logger = None


class _ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI colors per log level."""

    LEVEL_COLORS = {
        logging.DEBUG: Color.OKCYAN,
        logging.INFO: Color.ENDC,
        logging.WARNING: Color.WARNING,
        logging.ERROR: Color.FAIL,
        logging.CRITICAL: Color.FAIL + Color.BOLD,
    }

    def format(self, record):
        msg = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno, "")
        return f"{color}{msg}{Color.ENDC}" if color else msg


def setup_logging(log_file=None, level=logging.INFO):
    """Initialize logging — console (colored) + optional file handler.

    Returns the root logger. Safe to call multiple times (idempotent).
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("comfyui_setup")
    logger.setLevel(level)
    logger.propagate = False

    # Console handler — colored, compact
    console_fmt = _ColoredFormatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler — full timestamps, plain text
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger():
    """Return existing logger, or create a console-only one."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


# ── Helpers ──
def print_header(msg, char="="):
    """Print a bold section header with dividers."""
    log = get_logger()
    log.info("")
    log.info(f"{Color.BOLD}{Color.OKCYAN}{char * 55}{Color.ENDC}")
    log.info(f"{Color.BOLD}{Color.OKCYAN}  {msg}{Color.ENDC}")
    log.info(f"{Color.BOLD}{Color.OKCYAN}{char * 55}{Color.ENDC}")
    log.info("")


def timer():
    """Simple context manager for timing operations."""

    class _Timer:
        def __init__(self):
            self.elapsed = 0

        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, *_):
            self.elapsed = time.time() - self.start

    return _Timer()


def run_cmd(command, cwd=None, quiet=False, timeout=600):
    """Run a shell command. Returns True on success, False on failure.

    Logs command, timing, and errors. Uses stdout=PIPE when quiet so failures
    are captured without flooding the terminal.
    """
    log = get_logger()
    if not quiet:
        log.info(f"  $ {command[:120]}{'...' if len(command) > 120 else ''}")

    try:
        with timer() as t:
            subprocess.run(
                command,
                shell=True,
                check=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL if quiet else subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=True,
            )
        if not quiet:
            log.info(f"  -> ok ({t.elapsed:.1f}s)")
        return True
    except subprocess.CalledProcessError as e:
        log.warning(f"  -> failed ({e.returncode})")
        if e.stderr:
            for line in e.stderr.strip().splitlines()[-5:]:
                log.warning(f"    {line}")
        return False
    except subprocess.TimeoutExpired:
        log.error(f"  -> timed out after {timeout}s")
        return False


def check_server_ready(port, timeout=120):
    """Poll a TCP port until ComfyUI is ready. Returns True on success."""
    import socket

    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=1)
            sock.close()
            get_logger().info(
                f"{Color.OKGREEN}Server ready on port {port} ({time.time() - start:.0f}s){Color.ENDC}"
            )
            return True
        except Exception:
            time.sleep(0.5)

    get_logger().error(f"Server did not start within {timeout}s")
    return False


def start_comfyui(extra_args="", port=8188):
    """Start ComfyUI as a background process and wait until it's ready."""
    workspace = Path(os.environ.get("WORKSPACE", "/content"))
    comfy_dir = workspace / "ComfyUI"

    cmd = f"python {comfy_dir}/main.py --listen 0.0.0.0 --port {port} {extra_args}"
    log = get_logger()
    log.info(f"Starting ComfyUI...")
    log.info(f"  $ {cmd}")

    proc = subprocess.Popen(cmd, shell=True, cwd=str(comfy_dir))
    check_server_ready(port)
    return proc
