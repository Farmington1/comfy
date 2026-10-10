"""Validate YAML configuration files and their internal consistency."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"

ALLOWED_DESTS = {
    "diffusion_models", "text_encoders", "vae", "loras", "clip_vision", "unet",
}


def _load(name):
    with (CONFIG / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_yaml_files_parse():
    for name in ("settings.yaml", "models.yaml", "custom_nodes.yaml"):
        data = _load(name)
        assert isinstance(data, dict), f"{name} must parse to a mapping"


def test_settings_required_keys():
    s = _load("settings.yaml")
    assert s["comfyui"]["repo"].startswith("https://")
    assert s["comfyui"]["version"], "ComfyUI version must be pinned"
    assert s["comfyui"]["install_dir"]
    for key in ("models_dir", "input_dir", "output_dir", "logs_dir"):
        assert key in s["paths"]
    assert s["server"]["port"]
    assert s["project"]["default_tier"] in _load("models.yaml")["tiers"]
    # GPU profiles must be ordered high -> low and complete.
    profiles = s["gpu"]["profiles"]
    mins = [p["min_vram_gib"] for p in profiles]
    assert mins == sorted(mins, reverse=True), "profiles must be descending"
    assert mins[-1] == 0, "there must be a catch-all profile (min 0)"


def test_models_entries_well_formed():
    m = _load("models.yaml")
    for key, entry in m["models"].items():
        for field in ("filename", "dest", "url", "suburl", "size"):
            assert field in entry, f"model {key} missing {field}"
        assert entry["dest"] in ALLOWED_DESTS, f"{key}: bad dest {entry['dest']}"
        assert str(entry["url"]).startswith("https://"), f"{key}: bad url"
        assert int(entry["size"]) > 0, f"{key}: size must be positive"
        assert entry["suburl"].startswith("/"), f"{key}: suburl must start with /"


def test_tiers_reference_existing_models():
    m = _load("models.yaml")
    keys = set(m["models"])
    for tier, members in m["tiers"].items():
        for k in members:
            assert k in keys, f"tier '{tier}' references unknown model '{k}'"


def test_base_tier_is_self_sufficient():
    """The default/base tier must include an encoder, a VAE and a diffusion model."""
    m = _load("models.yaml")
    dests = {m["models"][k]["dest"] for k in m["tiers"]["base"]}
    assert "text_encoders" in dests
    assert "vae" in dests
    assert "diffusion_models" in dests


def test_custom_nodes_pinned():
    n = _load("custom_nodes.yaml")
    for node in n["nodes"]:
        assert node["repo"].startswith("https://")
        assert node.get("commit"), f"{node['name']} must pin a commit"
