"""Tunnel launchers — Cloudflare, LocalTunnel, Ngrok."""

import re
import subprocess
import threading

from .ui import Color, get_logger


def start_cloudflare(port=8188):
    """Start Cloudflare quick tunnel."""
    log = get_logger()

    subprocess.run(
        "curl -sL --output /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb",
        shell=True,
        check=True,
    )
    subprocess.run("dpkg -i /tmp/cf.deb > /dev/null 2>&1", shell=True, check=True)
    subprocess.run("rm -f /tmp/cf.deb", shell=True)
    log.info(f"Cloudflared installed")

    def run_tunnel():
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--protocol", "http2", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        url_found = threading.Event()
        for line in proc.stdout:
            line = line.rstrip()
            log.info(f"  {line}")
            match = re.search(r"(https://[a-zA-Z0-9.-]+\.trycloudflare\.com)", line)
            if match and not url_found.is_set():
                url_found.set()
                log.info(f"  {Color.BOLD}Cloudflare URL: {match.group(1)}{Color.ENDC}")
                log.info(f"  {Color.WARNING}URL changes on each restart{Color.ENDC}")

    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()


def start_localtunnel(port=8188):
    """Start LocalTunnel."""
    log = get_logger()

    subprocess.run("npm install -g localtunnel > /dev/null 2>&1", shell=True, check=True)
    log.info("LocalTunnel installed")

    import urllib.request

    def run_tunnel():
        try:
            ip = urllib.request.urlopen("https://ipv4.icanhazip.com").read().decode("utf8").strip()
            log.info(f"  Your IP (entry password): {Color.BOLD}{ip}{Color.ENDC}")
        except Exception:
            log.warning("  Could not fetch IP")

        proc = subprocess.Popen(
            ["lt", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            line = line.rstrip()
            log.info(f"  {line}")
            if "your url is" in line.lower():
                break

    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()


def start_ngrok(auth_token=None, port=8188):
    """Start Ngrok tunnel."""
    log = get_logger()
    import os

    subprocess.run("pip install -q pyngrok", shell=True, check=True)
    log.info("pyngrok installed")

    if not auth_token:
        auth_token = os.environ.get("NGROK_AUTH_TOKEN", "")

    from pyngrok import ngrok

    if auth_token:
        ngrok.set_auth_token(auth_token)
