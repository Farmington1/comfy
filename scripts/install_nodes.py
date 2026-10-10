#!/usr/bin/env python3
"""Install ComfyUI custom nodes defined in config/custom_nodes.yaml.

The four core workflows need NO custom nodes, so by default this installs
nothing. A node is installed when:
  * it is marked `required: true`, OR
  * one of its `needed_for_tiers` matches the selected/`--tier` tier, OR
  * it is named explicitly via `--node <key>`.

Each node is pinned to an exact commit. Re-running is idempotent.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import common as c


def run(cmd, cwd=None, check=True):
    c.info("$ " + " ".join(str(x) for x in cmd))
    rc = subprocess.run(cmd, cwd=cwd, text=True).returncode
    if check and rc != 0:
        c.fail(f"Command failed ({rc}): {' '.join(map(str, cmd))}")
    return rc


def install_node(node: Dict, custom_nodes_dir: Path) -> None:
    dest = custom_nodes_dir / node["name"]
    if (dest / ".git").exists():
        c.ok(f"{node['name']} already installed (skipping).")
    else:
        c.step(f"Installing custom node: {node['name']}")
        run(["git", "clone", "--filter=blob:none", node["repo"], str(dest)])

    ref = node.get("commit")
    if ref:
        run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref],
            check=False)
        if run(["git", "-C", str(dest), "checkout", "--quiet", ref],
               check=False) != 0:
            run(["git", "-C", str(dest), "fetch", "origin"], check=False)
            run(["git", "-C", str(dest), "checkout", "--quiet", ref])

    if node.get("pip_requirements"):
        req = dest / "requirements.txt"
        if req.exists():
            run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                check=False)
    c.ok(f"{node['name']} ready.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default=None, help="model tier being used")
    ap.add_argument("--node", action="append", default=[],
                    help="force-install a node by key (repeatable)")
    ap.add_argument("--all", action="store_true", help="install every node")
    args = ap.parse_args()

    settings = c.load_settings()
    tier = args.tier or c.selected_tier(settings)
    cfg = c.load_custom_nodes()
    nodes: List[Dict] = cfg.get("nodes", [])

    custom_nodes_dir = c.comfy_install_dir(settings) / "custom_nodes"
    custom_nodes_dir.mkdir(parents=True, exist_ok=True)

    selected = []
    for node in nodes:
        want = (
            args.all
            or node.get("required")
            or node["key"] in args.node
            or tier in (node.get("needed_for_tiers") or [])
        )
        if want:
            selected.append(node)

    if not selected:
        c.ok(f"No custom nodes required for tier '{tier}'. "
             "(Core workflows use native nodes only.)")
        return 0

    for node in selected:
        install_node(node, custom_nodes_dir)

    c.ok(f"Installed {len(selected)} custom node(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
