#!/usr/bin/env python3
"""Synchronise persistent data with Google Drive (safe, non-destructive).

Creates the Drive folder tree:
    MyDrive/AI-Video-Studio/{models,workflows,inputs,outputs,configs,logs}

and syncs useful artefacts between the fast local Colab disk and Drive:

  * configs   : repo config/*.yaml  -> Drive (push, overwrite ok)
  * workflows : repo workflows/*.json -> Drive, but NEVER overwrites a file
                the user has customised in Drive (push-if-absent/identical)
  * inputs    : Drive -> local ComfyUI/input (pull reference images)
  * outputs   : local ComfyUI/output -> Drive (push generated videos, never
                overwrite an existing Drive file of the same name)
  * logs      : local logs -> Drive (push)

Model weights are handled by download_models.py (Drive cache), not here, to
avoid copying tens of GB unnecessarily. Files are compared by size so we
skip unnecessary copies. User-created outputs/workflows are never clobbered.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional

import common as c


def drive_root(settings) -> Optional[Path]:
    use = c.env("AVS_USE_DRIVE", "1" if settings["drive"]["enabled"] else "0")
    if use != "1":
        c.info("Drive persistence disabled (AVS_USE_DRIVE=0).")
        return None
    mount = c.env("AVS_DRIVE_MOUNT", settings["drive"]["mount_point"])
    root = c.env("AVS_DRIVE_ROOT", settings["drive"]["root"])
    if not Path(mount).exists():
        c.warn(f"Google Drive is not mounted at {mount}. "
               f"Mount it first (see the notebook) or set AVS_USE_DRIVE=0.")
        return None
    return Path(mount) / "MyDrive" / root


def ensure_tree(root: Path, settings) -> None:
    for sub in settings["drive"]["subdirs"]:
        (root / sub).mkdir(parents=True, exist_ok=True)
    c.ok(f"Drive folder tree ready at {root}")


def _same(a: Path, b: Path) -> bool:
    return (a.exists() and b.exists()
            and a.stat().st_size == b.stat().st_size)


def _copy(src: Path, dst: Path, protect: bool) -> str:
    if dst.exists():
        if _same(src, dst):
            return "skip (identical)"
        if protect:
            return "keep (user file preserved)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copied"


def push_dir(src_dir: Path, dst_dir: Path, pattern: str, protect: bool) -> None:
    if not src_dir.exists():
        return
    for src in sorted(src_dir.glob(pattern)):
        if src.is_file():
            action = _copy(src, dst_dir / src.name, protect)
            c.info(f"  {src.name}: {action}")


def pull_dir(src_dir: Path, dst_dir: Path, pattern: str) -> None:
    if not src_dir.exists():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob(pattern)):
        if src.is_file():
            action = _copy(src, dst_dir / src.name, protect=False)
            c.info(f"  {src.name}: {action}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--init", action="store_true",
                    help="only create the Drive folder tree")
    args = ap.parse_args()

    settings = c.load_settings()
    root = drive_root(settings)
    if root is None:
        return 0

    ensure_tree(root, settings)
    if args.init:
        return 0

    install = c.comfy_install_dir(settings)

    c.step("configs: repo -> Drive")
    push_dir(c.CONFIG_DIR, root / "configs", "*.yaml", protect=False)

    c.step("workflows: repo -> Drive (preserving user edits)")
    push_dir(c.WORKFLOWS_DIR, root / "workflows", "*.json", protect=True)

    c.step("inputs: Drive -> local ComfyUI/input")
    pull_dir(root / "inputs", install / settings["paths"]["input_dir"], "*")

    c.step("outputs: local ComfyUI/output -> Drive (never overwrite)")
    out_local = install / settings["paths"]["output_dir"]
    push_dir(out_local, root / "outputs", "**/*.mp4", protect=True)
    push_dir(out_local, root / "outputs", "**/*.webm", protect=True)

    c.step("logs: local -> Drive")
    push_dir(Path(settings["paths"]["logs_dir"]), root / "logs", "*", protect=False)

    c.ok("Storage sync complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
