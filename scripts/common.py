"""Shared helpers for AI Video Studio scripts.

Centralises configuration loading, path resolution, environment-variable
overrides and small logging/formatting utilities so every script behaves
consistently inside Google Colab and on a local machine.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - gives an actionable message
    print(
        "[ERROR] PyYAML is not installed. Run:  pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
WORKFLOWS_DIR = REPO_ROOT / "workflows"


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} did not parse to a mapping.")
    return data


def load_settings() -> Dict[str, Any]:
    return _read_yaml(CONFIG_DIR / "settings.yaml")


def load_models() -> Dict[str, Any]:
    return _read_yaml(CONFIG_DIR / "models.yaml")


def load_custom_nodes() -> Dict[str, Any]:
    return _read_yaml(CONFIG_DIR / "custom_nodes.yaml")


# --------------------------------------------------------------------------
# Environment / overrides
# --------------------------------------------------------------------------
def env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, treating empty strings as unset."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def comfy_install_dir(settings: Optional[Dict[str, Any]] = None) -> Path:
    settings = settings or load_settings()
    return Path(settings["comfyui"]["install_dir"]).expanduser()


def models_root(settings: Optional[Dict[str, Any]] = None) -> Path:
    settings = settings or load_settings()
    install = comfy_install_dir(settings)
    models_dir = settings["paths"]["models_dir"]
    p = Path(models_dir)
    return p if p.is_absolute() else install / p


def server_url(settings: Optional[Dict[str, Any]] = None) -> str:
    settings = settings or load_settings()
    host = env("AVS_COMFY_HOST", settings["server"]["host"])
    port = env("AVS_COMFY_PORT", str(settings["server"]["port"]))
    return f"http://{host}:{port}"


def selected_tier(settings: Optional[Dict[str, Any]] = None) -> str:
    settings = settings or load_settings()
    return env("AVS_MODEL_TIER", settings["project"]["default_tier"])


# --------------------------------------------------------------------------
# Logging / formatting
# --------------------------------------------------------------------------
_START = time.time()


def _ts() -> str:
    return f"[{time.time() - _START:6.1f}s]"


def step(msg: str) -> None:
    print(f"{_ts()} ==> {msg}", flush=True)


def info(msg: str) -> None:
    print(f"{_ts()}     {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"{_ts()}  OK  {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"{_ts()}  !!  WARNING: {msg}", flush=True)


def error(msg: str) -> None:
    print(f"{_ts()}  XX  ERROR: {msg}", file=sys.stderr, flush=True)


def fail(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    """Print an actionable error and exit non-zero (never silently skip)."""
    error(msg)
    sys.exit(code)


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PiB"


def in_colab() -> bool:
    return "google.colab" in sys.modules or env("COLAB_RELEASE_TAG") is not None
