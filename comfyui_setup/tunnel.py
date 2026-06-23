"""Tunnel launchers — Cloudflare, LocalTunnel, Ngrok."""

import subprocess
import threading

from .ui import Color


def start_cloudflare(port=8188):
    """Start Cloudflare quick tunnel."""
    # Install cloudflared
    subprocess.run(
        "curl -sL --output /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb",
        shell=True, check=True,
    )
    subprocess.run("dpkg -i /tmp/cf.deb > /dev/null 2>&1", shell=True, check=True)
    subprocess.run("rm -f /tmp/cf.deb", shell=True)
    print(f"  {Color.OKGREEN}✅ Cloudflared installed{Color.ENDC}\n")

    import re

    def run_tunnel():
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--protocol", "http2", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        url_found = threading.Event()
        for line in proc.stdout:
            print(f"  {line.rstrip()}")
            match = re.search(r"(https://[a-zA-Z0-9.-]+\.trycloudflare\.com)", line)
            if match and not url_found.is_set():
                url_found.set()
                print(f"\n  {Color.BOLD}🌐 Cloudflare URL: {match.group(1)}{Color.ENDC}")
                print(f"  {Color.WARNING}⚠️  URL changes on each restart{Color.ENDC}\n")

    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()


def start_localtunnel(port=8188):
    """Start LocalTunnel."""
    subprocess.run("npm install -g localtunnel > /dev/null 2>&1", shell=True, check=True)
    print(f"  {Color.OKGREEN}✅ LocalTunnel installed{Color.ENDC}\n")

    import urllib.request

    def run_tunnel():
        try:
            ip = urllib.request.urlopen("https://ipv4.icanhazip.com").read().decode("utf8").strip()
            print(f"  🔑 Your IP (entry password): {Color.BOLD}{ip}{Color.ENDC}")
        except Exception:
            print(f"  {Color.WARNING}⚠️  Could not fetch IP{Color.ENDC}")

        proc = subprocess.Popen(
            ["lt", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            print(f"  {line.rstrip()}")
            if "your url is" in line.lower():
                break

    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()


def start_ngrok(auth_token=None, port=8188):
    """Start Ngrok tunnel."""
    subprocess.run("pip install -q pyngrok", shell=True, check=True)
    print(f"  {Color.OKGREEN}✅ pyngrok installed{Color.ENDC}\n")

    if not auth_token:
        import os
        auth_token = os.environ.get("NGROK_AUTH_TOKEN", "")

    if auth_token:
        from pyngrok import ngrok
        ngrok.set_auth_token(auth_token)
        tunnel = ngrok.connect(port, "http")
        print(f"  {Color.BOLD}🌐 Ngrok URL: {tunnel.public_url}{Color.ENDC}\n")
    else:
        print(f"  {Color.WARNING}⚠️  No NGROK_AUTH_TOKEN — using free tier (limited){Color.ENDC}")
        from pyngrok import ngrok
        tunnel = ngrok.connect(port, "http")
        print(f"  {Color.BOLD}🌐 Ngrok URL: {tunnel.public_url}{Color.ENDC}\n")
