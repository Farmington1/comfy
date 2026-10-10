"""Structural validation: scripts compile, notebook is valid, layout is intact."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
NOTEBOOK = ROOT / "colab" / "ComfyUI_Video_Generation.ipynb"

EXPECTED_SCRIPTS = [
    "common.py", "setup.py", "install_comfyui.py", "install_nodes.py",
    "download_models.py", "validate_environment.py", "launch_comfyui.py",
    "sync_storage.py", "generate.py",
]


def test_expected_layout_exists():
    assert (ROOT / "README.md").exists()
    assert (ROOT / "AGENTS.md").exists()
    assert (ROOT / ".gitignore").exists()
    assert (ROOT / ".env.example").exists()
    assert (ROOT / "requirements.txt").exists()
    assert NOTEBOOK.exists()
    for d in ("scripts", "config", "workflows", "docs", "tests", "colab"):
        assert (ROOT / d).is_dir(), f"missing directory {d}"


@pytest.mark.parametrize("script", EXPECTED_SCRIPTS)
def test_scripts_present_and_compile(script):
    path = SCRIPTS / script
    assert path.exists(), f"missing script {script}"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)  # raises SyntaxError on invalid Python


def test_docs_present():
    for doc in ("QUICK_START.md", "MODELS.md", "TROUBLESHOOTING.md"):
        assert (ROOT / "docs" / doc).exists(), f"missing doc {doc}"


def test_notebook_structure_valid():
    with NOTEBOOK.open(encoding="utf-8") as fh:
        nb = json.load(fh)
    assert nb.get("nbformat") == 4
    assert isinstance(nb.get("cells"), list) and nb["cells"], "no cells"
    for cell in nb["cells"]:
        assert cell["cell_type"] in ("markdown", "code")
        assert isinstance(cell["source"], list)
        if cell["cell_type"] == "code":
            assert "outputs" in cell and "execution_count" in cell
    # Must reference the key scripts/workflows so it actually drives the system.
    text = json.dumps(nb)
    for needle in ("scripts/setup.py", "validate_environment.py",
                   "run_generation", "launch_comfyui.py"):
        assert needle in text, f"notebook does not reference {needle}"
    # GPU accelerator metadata.
    assert nb["metadata"].get("accelerator") == "GPU"


def test_common_module_importable():
    sys.path.insert(0, str(SCRIPTS))
    import common  # noqa: WPS433
    settings = common.load_settings()
    assert settings["comfyui"]["version"]
    models = common.load_models()
    assert "base" in models["tiers"]
    # Helper sanity.
    assert common.human_size(1024) == "1.0 KiB"


def test_gitignore_blocks_weights_and_secrets():
    gi = (ROOT / ".gitignore").read_text()
    for pattern in ("*.safetensors", "*.gguf", ".env", "ComfyUI/", "outputs/"):
        assert pattern in gi, f".gitignore should contain {pattern}"
