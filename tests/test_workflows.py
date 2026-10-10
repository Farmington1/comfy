"""Validate the ComfyUI workflow definitions against the model manifest.

Ensures there are no placeholder nodes, dangling links, unknown parameters, or
model references that don't exist in config/models.yaml - i.e. that each
workflow could actually run on a correctly-installed ComfyUI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / "workflows"
CONFIG = ROOT / "config"

REQUIRED_WORKFLOWS = [
    "wan_text_to_video",
    "wan_image_to_video",
    "fast_preview",
    "high_quality",
]

# Native ComfyUI node types used by the workflows (no custom nodes).
KNOWN_CLASS_TYPES = {
    "UNETLoader", "CLIPLoader", "VAELoader", "ModelSamplingSD3",
    "CLIPTextEncode", "Wan22ImageToVideoLatent", "EmptyHunyuanLatentVideo",
    "LoadImage", "KSampler", "KSamplerAdvanced", "VAEDecode",
    "CreateVideo", "SaveVideo", "LoraLoaderModelOnly",
}

# input names that reference a model file -> which part they live in
MODEL_INPUTS = {"unet_name", "clip_name", "vae_name", "lora_name"}


def _models_cfg():
    with (CONFIG / "models.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _all_model_filenames():
    return {e["filename"] for e in _models_cfg()["models"].values()}


def _tier_filenames(tier):
    m = _models_cfg()
    return {m["models"][k]["filename"] for k in m["tiers"][tier]}


def _load_wf(name):
    with (WORKFLOWS / f"{name}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_workflow_exists_and_parses(name):
    assert (WORKFLOWS / f"{name}.json").exists(), f"missing workflow {name}"
    wf = _load_wf(name)
    for key in ("name", "description", "tier", "mode", "meta", "prompt"):
        assert key in wf, f"{name} missing top-level key '{key}'"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_prompt_nodes_valid(name):
    wf = _load_wf(name)
    prompt = wf["prompt"]
    assert prompt, f"{name} has empty prompt"
    for node_id, node in prompt.items():
        assert "class_type" in node, f"{name}:{node_id} missing class_type"
        assert node["class_type"] in KNOWN_CLASS_TYPES, \
            f"{name}:{node_id} unknown class_type {node['class_type']}"
        assert "inputs" in node, f"{name}:{node_id} missing inputs"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_links_point_to_existing_nodes(name):
    wf = _load_wf(name)
    prompt = wf["prompt"]
    for node_id, node in prompt.items():
        for input_name, value in node["inputs"].items():
            # A link is encoded as [node_id, output_slot].
            if isinstance(value, list) and len(value) == 2 \
                    and isinstance(value[0], str) and isinstance(value[1], int):
                target = value[0]
                assert target in prompt, \
                    f"{name}:{node_id}.{input_name} links to missing node {target}"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_model_references_exist(name):
    wf = _load_wf(name)
    all_files = _all_model_filenames()
    for node_id, node in wf["prompt"].items():
        for input_name, value in node["inputs"].items():
            if input_name in MODEL_INPUTS and isinstance(value, str):
                assert value in all_files, (
                    f"{name}:{node_id}.{input_name} references '{value}' which "
                    f"is not in config/models.yaml"
                )


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_model_references_match_declared_tier(name):
    """Every model a workflow loads must be downloadable via its declared tier."""
    wf = _load_wf(name)
    tier = wf["tier"]
    tier_files = _tier_filenames(tier)
    for node_id, node in wf["prompt"].items():
        for input_name, value in node["inputs"].items():
            if input_name in MODEL_INPUTS and isinstance(value, str):
                assert value in tier_files, (
                    f"{name}:{node_id} loads '{value}' but it is not in tier "
                    f"'{tier}'. Add it to that tier in config/models.yaml."
                )


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_meta_param_map_consistent(name):
    wf = _load_wf(name)
    prompt = wf["prompt"]
    params = wf["meta"]["params"]
    for pname, targets in params.items():
        assert isinstance(targets, list) and targets, \
            f"{name}: param '{pname}' must map to a non-empty list"
        for pair in targets:
            assert isinstance(pair, list) and len(pair) == 2, \
                f"{name}: param '{pname}' entries must be [node_id, input_name]"
            node_id, input_name = pair
            assert node_id in prompt, \
                f"{name}: param '{pname}' -> missing node {node_id}"
            assert input_name in prompt[node_id]["inputs"], \
                f"{name}: param '{pname}' -> node {node_id} has no input "\
                f"'{input_name}'"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_defaults_are_patchable(name):
    wf = _load_wf(name)
    params = set(wf["meta"]["params"])
    for key in wf["meta"].get("defaults", {}):
        assert key in params, \
            f"{name}: default '{key}' has no entry in meta.params"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_length_is_4n_plus_1(name):
    wf = _load_wf(name)
    length = wf["meta"].get("defaults", {}).get("length")
    if length is not None:
        assert (length - 1) % 4 == 0, \
            f"{name}: length {length} must be 4n+1 for Wan"


@pytest.mark.parametrize("name", REQUIRED_WORKFLOWS)
def test_clip_loader_uses_wan_type(name):
    wf = _load_wf(name)
    for node in wf["prompt"].values():
        if node["class_type"] == "CLIPLoader":
            assert node["inputs"].get("type") == "wan", \
                f"{name}: CLIPLoader must use type 'wan'"


def test_i2v_workflow_has_load_image():
    wf = _load_wf("wan_image_to_video")
    class_types = {n["class_type"] for n in wf["prompt"].values()}
    assert "LoadImage" in class_types
    assert "input_image" in wf["meta"]["params"]


def test_tiers_are_known():
    tiers = set(_models_cfg()["tiers"])
    for name in REQUIRED_WORKFLOWS:
        assert _load_wf(name)["tier"] in tiers
