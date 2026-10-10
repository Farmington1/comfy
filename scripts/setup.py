#!/usr/bin/env python3
"""One-command environment setup for AI Video Studio (Colab-friendly).

Orchestrates, in order:
    1. validate_environment  (detect GPU/VRAM; recommend a tier + VRAM flag)
    2. install_comfyui       (pinned clone + requirements)
    3. install_nodes         (only custom nodes the chosen tier needs)
    4. download_models       (only the chosen tier)
    5. sync_storage --init   (create the Drive folder tree + push configs)
    6. launch_comfyui start  (headless local API, unless --no-launch)

Design goals: idempotent, fails loudly with actionable messages, and never
silently skips a critical step. Safe to re-run.

Typical Colab usage:
    !python scripts/setup.py --tier auto
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import common as c

SCRIPTS = Path(__file__).resolve().parent


def run_script(name: str, extra: Optional[List[str]] = None,
               capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPTS / name), *(extra or [])]
    c.info("$ " + " ".join(cmd))
    return subprocess.run(cmd, text=True,
                          capture_output=capture)


def validate_and_recommend() -> dict:
    c.step("[1/6] Validating environment")
    proc = run_script("validate_environment.py", ["--json"], capture=True)
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    try:
        summary = json.loads(proc.stdout)
    except (ValueError, TypeError):
        c.warn("Could not parse environment summary; continuing with defaults.")
        return {}
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="auto",
                    help="base|quality|i2v_14b|gguf|auto (default: auto)")
    ap.add_argument("--vram-flag", default="auto",
                    help="ComfyUI VRAM flag, e.g. --lowvram (default: auto)")
    ap.add_argument("--no-launch", action="store_true",
                    help="set up everything but do not start the server")
    ap.add_argument("--no-drive", action="store_true",
                    help="skip Google Drive folder/sync setup")
    ap.add_argument("--skip-download", action="store_true",
                    help="skip model downloads (e.g. already cached)")
    args = ap.parse_args()

    settings = c.load_settings()
    summary = validate_and_recommend()

    # Resolve tier.
    tier = args.tier
    if tier == "auto":
        tier = summary.get("recommended_tier") or settings["project"]["default_tier"]
    c.ok(f"Using model tier: {tier}")

    # Resolve VRAM flag.
    vram_flag = args.vram_flag
    if vram_flag == "auto":
        vram_flag = summary.get("comfy_vram_flag", "") or ""
    if vram_flag:
        c.info(f"ComfyUI VRAM flag: {vram_flag}")

    # 2. Install ComfyUI.
    c.step("[2/6] Installing ComfyUI (pinned)")
    if run_script("install_comfyui.py").returncode != 0:
        c.fail("ComfyUI installation failed. See messages above.")

    # 3. Custom nodes for this tier.
    c.step("[3/6] Installing custom nodes (if any required)")
    if run_script("install_nodes.py", ["--tier", tier]).returncode != 0:
        c.fail("Custom node installation failed.")

    # 4. Models.
    if args.skip_download:
        c.warn("[4/6] Skipping model download (--skip-download).")
    else:
        c.step(f"[4/6] Downloading models for tier '{tier}'")
        if run_script("download_models.py", ["--tier", tier]).returncode != 0:
            c.fail("Model download failed. Re-run to resume partial downloads.")

    # 5. Drive tree.
    if args.no_drive:
        c.warn("[5/6] Skipping Google Drive setup (--no-drive).")
    else:
        c.step("[5/6] Preparing Google Drive persistence")
        run_script("sync_storage.py", ["--init"])  # non-fatal if unmounted

    # 6. Launch.
    if args.no_launch:
        c.ok("[6/6] Setup complete (server NOT started; --no-launch).")
        return 0
    c.step("[6/6] Launching ComfyUI (headless, localhost)")
    launch_args = ["start"]
    if vram_flag:
        launch_args += ["--vram-flag", vram_flag]
    if run_script("launch_comfyui.py", launch_args).returncode != 0:
        c.fail("ComfyUI did not start. See the log printed above.")

    c.ok("Setup complete. ComfyUI API is ready for generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
