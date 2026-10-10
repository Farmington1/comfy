#!/usr/bin/env python3
"""Drive a Wan 2.2 generation through ComfyUI's LOCAL HTTP API.

This is the Colab-ToS-compliant generation path: instead of interacting with
a web UI, we submit a workflow (API/prompt format) to the ComfyUI server
running on localhost and poll for the result from the notebook.

Pipeline:
  1. Load workflows/<name>.json  ({ "prompt": {...}, "meta": {...} }).
  2. Apply user parameters using the meta param-map.
  3. For i2v, copy the reference image into ComfyUI/input.
  4. POST /prompt, surface any node validation errors clearly.
  5. Poll /history/<id> until the job finishes.
  6. Locate the produced MP4 and (optionally) copy it to Google Drive.

Importable (run_generation) and runnable from the CLI.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import common as c

try:
    import requests
except ImportError:  # pragma: no cover
    c.fail("`requests` missing. Run: pip install -r requirements.txt")

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov", ".gif")


# --------------------------------------------------------------------------
# Workflow loading / patching
# --------------------------------------------------------------------------
def load_workflow(name: str) -> Dict[str, Any]:
    path = c.WORKFLOWS_DIR / (name if name.endswith(".json") else name + ".json")
    if not path.exists():
        avail = ", ".join(p.stem for p in c.WORKFLOWS_DIR.glob("*.json"))
        c.fail(f"Workflow '{name}' not found. Available: {avail}")
    with path.open(encoding="utf-8") as fh:
        wf = json.load(fh)
    if "prompt" not in wf or "meta" not in wf:
        c.fail(f"Workflow {path} missing 'prompt'/'meta' keys.")
    return wf


def apply_params(wf: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    prompt = json.loads(json.dumps(wf["prompt"]))  # deep copy
    pmap = wf["meta"]["params"]
    defaults = wf["meta"].get("defaults", {})

    merged = dict(defaults)
    merged.update({k: v for k, v in params.items() if v is not None})

    for key, value in merged.items():
        if key not in pmap:
            # Not every workflow exposes every parameter (e.g. no input_image
            # for t2v). Silently ignore unknown-but-defaulted keys.
            if key in defaults:
                continue
            c.warn(f"Workflow does not expose parameter '{key}'; ignoring.")
            continue
        for node_id, input_name in pmap[key]:
            if node_id not in prompt:
                c.fail(f"meta references missing node '{node_id}'.")
            prompt[node_id]["inputs"][input_name] = value
    return prompt


def stage_input_image(src: str, settings: Dict[str, Any]) -> str:
    """Copy a reference image into ComfyUI/input and return its basename."""
    src_path = Path(src).expanduser()
    if not src_path.exists():
        c.fail(f"Input image not found: {src_path}")
    input_dir = c.comfy_install_dir(settings) / settings["paths"]["input_dir"]
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / src_path.name
    if src_path.resolve() != dest.resolve():
        shutil.copy2(src_path, dest)
    c.info(f"Staged reference image -> {dest}")
    return src_path.name


# --------------------------------------------------------------------------
# ComfyUI API
# --------------------------------------------------------------------------
def submit(prompt: Dict[str, Any], settings: Dict[str, Any],
           client_id: str) -> str:
    url = c.server_url(settings) + "/prompt"
    payload = {"prompt": prompt, "client_id": client_id}
    try:
        r = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as exc:
        c.fail(f"Could not reach ComfyUI at {url}: {exc}. "
               f"Is the server running? (launch_comfyui.py start)")
    if r.status_code != 200:
        detail = _format_node_errors(r)
        c.fail(f"ComfyUI rejected the workflow (HTTP {r.status_code}).\n{detail}")
    data = r.json()
    if data.get("node_errors"):
        c.fail("Workflow validation errors:\n" +
               json.dumps(data["node_errors"], indent=2))
    return data["prompt_id"]


def _format_node_errors(resp) -> str:
    try:
        data = resp.json()
    except ValueError:
        return resp.text[:2000]
    out = []
    if data.get("error"):
        out.append(f"error: {json.dumps(data['error'], indent=2)}")
    if data.get("node_errors"):
        out.append(f"node_errors: {json.dumps(data['node_errors'], indent=2)}")
    return "\n".join(out) or json.dumps(data, indent=2)


def wait_for(prompt_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    base = c.server_url(settings)
    interval = settings["generation"]["poll_interval_sec"]
    timeout = settings["generation"]["job_timeout_sec"]
    deadline = time.time() + timeout
    start = time.time()
    last_note = 0.0

    while time.time() < deadline:
        try:
            r = requests.get(f"{base}/history/{prompt_id}", timeout=10)
            if r.status_code == 200:
                hist = r.json()
                if prompt_id in hist:
                    # ComfyUI only adds an entry once execution has finished
                    # (successfully or with an error).
                    entry = hist[prompt_id]
                    status = entry.get("status", {})
                    if status.get("status_str") == "error":
                        c.fail("Generation failed. Server messages:\n" +
                               json.dumps(status.get("messages", []), indent=2))
                    c.ok(f"Job finished in {time.time() - start:.0f}s.")
                    return entry
        except requests.RequestException:
            pass

        now = time.time()
        if now - last_note >= 10:
            c.info(f"  ...generating ({now - start:.0f}s elapsed)")
            last_note = now
        time.sleep(interval)

    c.fail(f"Generation timed out after {timeout}s.")
    return {}


def collect_outputs(entry: Dict[str, Any], settings: Dict[str, Any]
                    ) -> List[Path]:
    out_dir = c.comfy_install_dir(settings) / settings["paths"]["output_dir"]
    found: List[Path] = []
    for node_out in entry.get("outputs", {}).values():
        for value in node_out.values():
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict) and "filename" in item:
                    sub = item.get("subfolder", "")
                    p = out_dir / sub / item["filename"]
                    if p.suffix.lower() in VIDEO_EXTS and p.exists():
                        found.append(p)
    # De-dupe while preserving order.
    seen, uniq = set(), []
    for p in found:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def mirror_to_drive(paths: List[Path], settings: Dict[str, Any]
                    ) -> List[Path]:
    use = c.env("AVS_USE_DRIVE", "1" if settings["drive"]["enabled"] else "0")
    if use != "1":
        return []
    mount = c.env("AVS_DRIVE_MOUNT", settings["drive"]["mount_point"])
    root = c.env("AVS_DRIVE_ROOT", settings["drive"]["root"])
    if not Path(mount).exists():
        c.info("Google Drive not mounted; skipping Drive copy.")
        return []
    dest_dir = Path(mount) / "MyDrive" / root / "outputs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for p in paths:
        dest = dest_dir / p.name
        try:
            shutil.copy2(p, dest)
            saved.append(dest)
            c.ok(f"Saved to Google Drive: {dest}")
        except OSError as exc:
            c.warn(f"Could not copy {p.name} to Drive: {exc}")
    return saved


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def run_generation(workflow: str, params: Optional[Dict[str, Any]] = None,
                   settings: Optional[Dict[str, Any]] = None,
                   save_to_drive: bool = True) -> Dict[str, Any]:
    settings = settings or c.load_settings()
    params = dict(params or {})

    wf = load_workflow(workflow)
    if params.get("input_image") and "input_image" in wf["meta"]["params"]:
        params["input_image"] = stage_input_image(params["input_image"], settings)

    prompt = apply_params(wf, params)
    client_id = str(uuid.uuid4())

    c.step(f"Submitting '{wf.get('name', workflow)}' to ComfyUI")
    prompt_id = submit(prompt, settings, client_id)
    c.info(f"prompt_id = {prompt_id}")

    entry = wait_for(prompt_id, settings)
    local = collect_outputs(entry, settings)
    if not local:
        c.warn("Job finished but no video output file was found. "
               "Check ComfyUI/output and the server log.")
    else:
        for p in local:
            c.ok(f"Output: {p}  ({c.human_size(p.stat().st_size)})")

    drive = mirror_to_drive(local, settings) if save_to_drive else []
    return {"prompt_id": prompt_id, "local": local, "drive": drive}


def _parse_cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workflow", help="workflow name, e.g. wan_text_to_video")
    ap.add_argument("--prompt", dest="positive_prompt")
    ap.add_argument("--negative", dest="negative_prompt")
    ap.add_argument("--image", dest="input_image")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--length", type=int)
    ap.add_argument("--steps", type=int)
    ap.add_argument("--cfg", type=float)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--fps", type=int)
    ap.add_argument("--filename-prefix", dest="filename_prefix")
    ap.add_argument("--no-drive", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = _parse_cli()
    params = {k: v for k, v in vars(args).items()
              if k not in ("workflow", "no_drive") and v is not None}
    result = run_generation(args.workflow, params,
                            save_to_drive=not args.no_drive)
    return 0 if result["local"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
