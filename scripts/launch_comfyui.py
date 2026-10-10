#!/usr/bin/env python3
"""Launch the ComfyUI server headless on localhost (Colab-ToS compliant).

On the FREE Colab tier it is against Google's terms to expose a public web
UI (via ngrok/cloudflared). This script therefore starts ComfyUI bound to
127.0.0.1 and leaves it running in the background; generation is driven from
notebook cells through the LOCAL HTTP API (see scripts/generate.py).

Usage:
  python launch_comfyui.py start      # start + wait until ready (default)
  python launch_comfyui.py status     # check if the API answers
  python launch_comfyui.py stop       # terminate the background server
  python launch_comfyui.py --tunnel   # (PAID tiers only) also open a tunnel

The process is detached; stdout/stderr go to the logs dir. A pidfile is
written so `stop` can find it. Re-running `start` when already up is a no-op.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import common as c

try:
    import requests
except ImportError:  # pragma: no cover
    c.fail("`requests` missing. Run: pip install -r requirements.txt")


def _paths(settings):
    logs_dir = Path(settings["paths"]["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir, logs_dir / "comfyui.pid", logs_dir / "comfyui.log"


def is_up(settings) -> bool:
    try:
        r = requests.get(c.server_url(settings) + "/system_stats", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def read_pid(pidfile: Path):
    if pidfile.exists():
        try:
            return int(pidfile.read_text().strip())
        except ValueError:
            return None
    return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start(settings, vram_flag: str = "") -> int:
    logs_dir, pidfile, logfile = _paths(settings)
    if is_up(settings):
        c.ok(f"ComfyUI already running at {c.server_url(settings)}")
        return 0

    install = c.comfy_install_dir(settings)
    main_py = install / "main.py"
    if not main_py.exists():
        c.fail(f"ComfyUI not installed at {install}. Run install_comfyui.py first.")

    host = c.env("AVS_COMFY_HOST", settings["server"]["host"])
    port = c.env("AVS_COMFY_PORT", str(settings["server"]["port"]))
    extra = settings["server"].get("extra_args", "").split()
    vram_flag = vram_flag or c.env("AVS_COMFY_VRAM_FLAG", "")

    cmd = [sys.executable, str(main_py),
           "--listen", host, "--port", str(port), *extra]
    if vram_flag:
        cmd += vram_flag.split()

    c.step(f"Starting ComfyUI: {' '.join(cmd)}")
    c.info(f"Logs -> {logfile}")
    with open(logfile, "ab") as log:
        proc = subprocess.Popen(
            cmd, cwd=str(install), stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pidfile.write_text(str(proc.pid))

    timeout = int(settings["server"].get("startup_timeout_sec", 300))
    c.info(f"Waiting up to {timeout}s for the API to become ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = _tail(logfile)
            c.fail(
                f"ComfyUI exited early (code {proc.returncode}).\n"
                f"--- last log lines ---\n{tail}"
            )
        if is_up(settings):
            c.ok(f"ComfyUI is ready at {c.server_url(settings)}")
            return 0
        time.sleep(2)

    c.fail(
        f"ComfyUI did not become ready within {timeout}s. "
        f"Check the log: {logfile}\n--- last log lines ---\n{_tail(logfile)}"
    )
    return 1


def _tail(path: Path, n: int = 25) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "(no log)"


def stop(settings) -> int:
    _, pidfile, _ = _paths(settings)
    pid = read_pid(pidfile)
    if pid and pid_alive(pid):
        c.step(f"Stopping ComfyUI (pid {pid})")
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            os.kill(pid, signal.SIGTERM)
        time.sleep(3)
        if pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
        c.ok("Stopped.")
    else:
        c.info("No running ComfyUI process found.")
    pidfile.unlink(missing_ok=True)
    return 0


def status(settings) -> int:
    if is_up(settings):
        try:
            r = requests.get(c.server_url(settings) + "/system_stats", timeout=5)
            data = r.json()
            dev = (data.get("devices") or [{}])[0]
            c.ok(f"ComfyUI UP at {c.server_url(settings)}")
            c.info(f"Device: {dev.get('name')} | "
                   f"VRAM total: {dev.get('vram_total')} | "
                   f"free: {dev.get('vram_free')}")
        except requests.RequestException:
            c.ok("ComfyUI UP")
        return 0
    c.info("ComfyUI is DOWN.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", nargs="?", default="start",
                    choices=["start", "stop", "status"])
    ap.add_argument("--vram-flag", default="", help="e.g. --lowvram")
    ap.add_argument("--tunnel", action="store_true",
                    help="PAID Colab only: open a public tunnel (not ToS-safe "
                         "on the free tier)")
    args = ap.parse_args()
    settings = c.load_settings()

    if args.tunnel:
        c.warn(
            "Public tunnels (ngrok/cloudflared) violate Google Colab's free-tier "
            "terms, which prohibit interacting primarily via a web UI. Only use "
            "--tunnel on a PAID Colab plan with a positive compute-unit balance. "
            "This script does NOT open a tunnel automatically; see docs."
        )

    if args.action == "start":
        return start(settings, vram_flag=args.vram_flag)
    if args.action == "stop":
        return stop(settings)
    return status(settings)


if __name__ == "__main__":
    raise SystemExit(main())
