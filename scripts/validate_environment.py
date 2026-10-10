#!/usr/bin/env python3
"""Validate the runtime environment for AI Video Studio.

Checks (in order):
  1. GPU runtime connected
  2. NVIDIA GPU model
  3. GPU VRAM
  4. CUDA availability / version
  5. PyTorch GPU availability
  6. System RAM
  7. Disk space
  8. Which configured model tiers can realistically run
  9. Recommended default tier + ComfyUI VRAM flag
 10. Loud warnings when the environment is too small

Produces human-readable output and, with --json, a machine-readable summary
written to stdout (used by the notebook to drive the UI).

Exit code is 0 unless --strict is given and a hard requirement (a usable GPU)
is missing.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import common as c


def _run(cmd: List[str]) -> Optional[str]:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return None


def detect_gpu_nvidia_smi() -> Dict[str, Any]:
    """Return GPU info from nvidia-smi, or empty dict if unavailable."""
    q = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not q:
        return {}
    first = q.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 2:
        return {}
    try:
        vram_mib = float(parts[1])
    except ValueError:
        vram_mib = 0.0
    return {
        "name": parts[0],
        "vram_gib": round(vram_mib / 1024.0, 1),
        "driver": parts[2] if len(parts) > 2 else "unknown",
    }


def detect_torch() -> Dict[str, Any]:
    info: Dict[str, Any] = {"available": False}
    try:
        import torch  # type: ignore
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"PyTorch not importable: {exc}"
        return info
    info["torch_version"] = torch.__version__
    info["cuda_available"] = bool(torch.cuda.is_available())
    info["cuda_version"] = getattr(torch.version, "cuda", None)
    if torch.cuda.is_available():
        info["available"] = True
        try:
            props = torch.cuda.get_device_properties(0)
            info["name"] = props.name
            info["vram_gib"] = round(props.total_memory / (1024 ** 3), 1)
        except Exception:  # noqa: BLE001
            pass
    return info


def system_ram_gib() -> Optional[float]:
    try:
        import os

        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / (1024 ** 3), 1)
    except Exception:  # noqa: BLE001
        meminfo = _run(["cat", "/proc/meminfo"])
        if meminfo:
            for line in meminfo.splitlines():
                if line.startswith("MemTotal"):
                    kb = float(line.split()[1])
                    return round(kb / (1024 ** 2), 1)
        return None


def disk_free_gib(path: str = "/content") -> Optional[float]:
    target = path if shutil.os.path.exists(path) else "/"
    try:
        usage = shutil.disk_usage(target)
        return round(usage.free / (1024 ** 3), 1)
    except Exception:  # noqa: BLE001
        return None


def pick_profile(vram_gib: float, settings: Dict[str, Any]) -> Dict[str, Any]:
    for profile in settings["gpu"]["profiles"]:
        if vram_gib >= profile["min_vram_gib"]:
            return profile
    return settings["gpu"]["profiles"][-1]


def tier_runnable(vram_gib: float) -> Dict[str, bool]:
    """Rough guidance on which tiers fit the detected VRAM.

    ComfyUI offloads to RAM, so these are 'comfortable' thresholds, not hard
    limits. We stay conservative so we never over-promise.
    """
    return {
        "gguf": vram_gib >= 6,
        "base": vram_gib >= 12,     # 5B fp16 with --lowvram fits ~12 GB
        "quality": vram_gib >= 16,  # 14B fp8, offloaded; comfortable at 24+
        "i2v_14b": vram_gib >= 16,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit JSON summary")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if no usable GPU is detected",
    )
    args = ap.parse_args()

    settings = c.load_settings()
    gpu_cfg = settings["gpu"]
    summary: Dict[str, Any] = {"checks": {}, "warnings": [], "errors": []}

    if not args.json:
        c.step("Validating environment")

    # 1-5: GPU / CUDA / torch
    smi = detect_gpu_nvidia_smi()
    torch_info = detect_torch()

    gpu_name = smi.get("name") or torch_info.get("name")
    vram_gib = smi.get("vram_gib") or torch_info.get("vram_gib") or 0.0
    has_gpu = bool(gpu_name) and (smi or torch_info.get("cuda_available"))

    summary["checks"]["gpu_present"] = bool(has_gpu)
    summary["checks"]["gpu_name"] = gpu_name
    summary["checks"]["vram_gib"] = vram_gib
    summary["checks"]["driver"] = smi.get("driver")
    summary["checks"]["torch"] = torch_info

    if not args.json:
        if has_gpu:
            c.ok(f"GPU detected: {gpu_name}  ({vram_gib} GiB VRAM)")
            c.info(f"Driver: {smi.get('driver', 'unknown')}")
        else:
            c.error("No NVIDIA GPU detected.")
            c.info(
                "In Colab: Runtime -> Change runtime type -> Hardware "
                "accelerator -> GPU, then reconnect."
            )

        if torch_info.get("available"):
            c.ok(
                f"PyTorch {torch_info.get('torch_version')} with CUDA "
                f"{torch_info.get('cuda_version')} (GPU usable)."
            )
        elif "torch_version" in torch_info:
            c.warn(
                f"PyTorch {torch_info['torch_version']} present but CUDA not "
                "available to it."
            )
        else:
            c.info(
                "PyTorch not importable yet (normal before ComfyUI install)."
            )

    if not has_gpu:
        summary["errors"].append("No GPU runtime connected.")

    # 6: RAM
    ram = system_ram_gib()
    summary["checks"]["ram_gib"] = ram
    if ram is not None and not args.json:
        c.ok(f"System RAM: {ram} GiB")
    if ram is not None and ram < gpu_cfg["min_ram_gib_warn"]:
        summary["warnings"].append(
            f"Low system RAM ({ram} GiB); model offloading may fail."
        )

    # 7: Disk
    disk = disk_free_gib(settings["comfyui"]["install_dir"].rsplit("/", 1)[0])
    summary["checks"]["disk_free_gib"] = disk
    if disk is not None and not args.json:
        c.ok(f"Free disk: {disk} GiB")
    if disk is not None and disk < gpu_cfg["min_disk_gib_warn"]:
        summary["warnings"].append(
            f"Low disk space ({disk} GiB free). The base model tier needs "
            f"~17 GiB; quality needs ~35 GiB."
        )

    # 8-9: tiers + recommendation
    runnable = tier_runnable(vram_gib)
    profile = pick_profile(vram_gib, settings)
    summary["checks"]["tiers_runnable"] = runnable
    summary["recommended_tier"] = profile["recommended_tier"]
    summary["recommended_workflow"] = profile["recommended_workflow"]
    summary["comfy_vram_flag"] = profile["comfy_vram_flag"]
    summary["gpu_profile"] = profile["name"]

    if not args.json:
        c.step("Model tier guidance")
        for tier, can in runnable.items():
            mark = "runs" if can else "too small"
            c.info(f"  tier '{tier}': {mark}")
        c.ok(
            f"Recommended: tier='{profile['recommended_tier']}', "
            f"workflow='{profile['recommended_workflow']}', "
            f"vram_flag='{profile['comfy_vram_flag'] or '(default)'}'"
        )

    # 10: warnings
    if vram_gib and vram_gib < gpu_cfg["min_vram_gib_warn"]:
        summary["warnings"].append(
            f"VRAM {vram_gib} GiB is below the recommended minimum "
            f"({gpu_cfg['min_vram_gib_warn']} GiB). Use the 'gguf' tier and "
            f"fast_preview workflow, or a larger GPU."
        )

    if not args.json:
        for w in summary["warnings"]:
            c.warn(w)
        if not summary["warnings"]:
            c.ok("No blocking warnings.")

    if args.json:
        print(json.dumps(summary, indent=2))

    if args.strict and not has_gpu:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
