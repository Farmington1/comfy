#!/usr/bin/env python3
"""Install ComfyUI at the pinned version (idempotent).

- Clones the pinned ComfyUI repo/tag into comfyui.install_dir if absent.
- Checks out the exact pinned tag so repeated runs are reproducible.
- Installs ComfyUI's own requirements WITHOUT clobbering Colab's preinstalled,
  CUDA-enabled PyTorch (torch/torchvision/torchaudio are filtered out).
- Creates the model/input/output directory tree.

Re-running does NOT re-clone or reinstall unless something is missing.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import common as c

MODEL_SUBDIRS = [
    "diffusion_models",
    "text_encoders",
    "vae",
    "loras",
    "clip_vision",
    "unet",
]


def run(cmd, cwd=None, check=True):
    c.info("$ " + " ".join(str(x) for x in cmd))
    result = subprocess.run(cmd, cwd=cwd, text=True)
    if check and result.returncode != 0:
        c.fail(f"Command failed ({result.returncode}): {' '.join(map(str, cmd))}")
    return result.returncode


def git_clone_pinned(repo: str, ref: str, dest: Path) -> None:
    if (dest / ".git").exists():
        c.ok(f"ComfyUI already present at {dest} (skipping clone).")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        c.step(f"Cloning ComfyUI into {dest}")
        run(["git", "clone", "--filter=blob:none", repo, str(dest)])

    # Ensure we are exactly on the pinned ref.
    c.step(f"Checking out pinned ComfyUI ref: {ref}")
    run(["git", "-C", str(dest), "fetch", "--tags", "--depth", "1", "origin", ref],
        check=False)
    rc = run(["git", "-C", str(dest), "checkout", "--quiet", ref], check=False)
    if rc != 0:
        # Fall back to fetching the tag explicitly then checking out.
        run(["git", "-C", str(dest), "fetch", "--tags"], check=False)
        run(["git", "-C", str(dest), "checkout", "--quiet", ref])
    head = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    c.ok(f"ComfyUI at {ref} (HEAD {head}).")


def install_requirements(dest: Path) -> None:
    req = dest / "requirements.txt"
    if not req.exists():
        c.warn(f"No requirements.txt in {dest}; skipping.")
        return

    # Filter torch* lines: Colab already ships a matched CUDA build and we
    # must not downgrade/replace it.
    filtered = []
    for line in req.read_text(encoding="utf-8").splitlines():
        name = line.strip().lower()
        if name.startswith(("torch", "torchvision", "torchaudio")):
            c.info(f"Skipping '{line.strip()}' (using Colab's preinstalled build).")
            continue
        filtered.append(line)

    tmp_req = dest / "_avs_requirements_no_torch.txt"
    tmp_req.write_text("\n".join(filtered) + "\n", encoding="utf-8")

    c.step("Installing ComfyUI Python requirements (reusing Colab torch)")
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(tmp_req)])
    c.ok("ComfyUI requirements installed.")


def ensure_model_dirs(dest: Path) -> None:
    base = dest / "models"
    for sub in MODEL_SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    (dest / "input").mkdir(parents=True, exist_ok=True)
    (dest / "output").mkdir(parents=True, exist_ok=True)
    c.ok(f"Model/input/output directories ready under {dest}.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-requirements", action="store_true")
    args = ap.parse_args()

    settings = c.load_settings()
    cm = settings["comfyui"]
    dest = c.comfy_install_dir(settings)
    ref = cm.get("version") or cm.get("commit")

    git_clone_pinned(cm["repo"], ref, dest)
    ensure_model_dirs(dest)
    if not args.skip_requirements:
        install_requirements(dest)

    c.ok(f"ComfyUI install complete at {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
