#!/usr/bin/env python3
"""Download Wan 2.2 model weights for a given tier (idempotent).

Features
--------
* Only downloads what a tier needs (default tier from settings).
* Skips files already present with the correct size (integrity check).
* Resumes partial downloads via HTTP Range when the server supports it.
* Optional Google Drive cache: if a correct copy exists in the Drive model
  cache it is COPIED locally (fast-ish) instead of re-downloaded; freshly
  downloaded files are mirrored back to Drive.
* --verify-urls does a HEAD request for every file and checks the size,
  without downloading (used by tests / CI-style validation).

Never commits weights. Never deletes user files.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

import common as c

try:
    import requests
except ImportError:  # pragma: no cover
    c.fail("`requests` missing. Run: pip install -r requirements.txt")


def resolve_url(model: Dict) -> str:
    base = model["url"].rstrip("/")
    sub = model.get("suburl", "")
    return base + sub


def tier_models(models_cfg: Dict, tier: str) -> List[str]:
    tiers = models_cfg.get("tiers", {})
    if tier not in tiers:
        c.fail(f"Unknown tier '{tier}'. Available: {', '.join(tiers)}")
    return tiers[tier]


def dest_path(models_cfg_entry: Dict, settings: Dict) -> Path:
    root = c.models_root(settings)
    return root / models_cfg_entry["dest"] / models_cfg_entry["filename"]


def drive_cache_path(entry: Dict, settings: Dict) -> Optional[Path]:
    if not settings["drive"].get("cache_models"):
        return None
    mount = c.env("AVS_DRIVE_MOUNT", settings["drive"]["mount_point"])
    root = c.env("AVS_DRIVE_ROOT", settings["drive"]["root"])
    use = c.env("AVS_USE_DRIVE", "1" if settings["drive"]["enabled"] else "0")
    if use != "1":
        return None
    drive_models = Path(mount) / "MyDrive" / root / "models"
    if not Path(mount).exists():
        return None
    return drive_models / entry["dest"] / entry["filename"]


def correct_size(path: Path, expected: int) -> bool:
    return path.exists() and expected > 0 and path.stat().st_size == expected


def _auth_headers() -> Dict[str, str]:
    token = c.env("HF_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def head_size(url: str) -> Optional[int]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=30,
                          headers=_auth_headers())
        if r.status_code == 200 and "Content-Length" in r.headers:
            return int(r.headers["Content-Length"])
        # HF resolve often needs GET with stream to reveal size
        r = requests.get(url, stream=True, timeout=30, headers=_auth_headers())
        if r.status_code == 200 and "Content-Length" in r.headers:
            size = int(r.headers["Content-Length"])
            r.close()
            return size
    except requests.RequestException:
        return None
    return None


def stream_download(url: str, dest: Path, expected: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    resume_from = tmp.stat().st_size if tmp.exists() else 0
    headers = _auth_headers()
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
        c.info(f"Resuming from {c.human_size(resume_from)}")

    with requests.get(url, stream=True, timeout=60, headers=headers) as r:
        if r.status_code == 416:  # range not satisfiable -> restart cleanly
            tmp.unlink(missing_ok=True)
            with requests.get(url, stream=True, timeout=60,
                              headers=_auth_headers()) as r2:
                if r2.status_code != 200:
                    c.fail(f"Download failed HTTP {r2.status_code}: {url}")
                _write(r2, tmp, 0, expected)
        elif r.status_code == 206:  # partial content -> safe to append
            _write(r, tmp, resume_from, expected)
        elif r.status_code == 200:  # server ignored Range -> full file, restart
            _write(r, tmp, 0, expected)
        else:
            c.fail(f"Download failed HTTP {r.status_code}: {url}")

    final_size = tmp.stat().st_size
    if expected and final_size != expected:
        c.fail(
            f"Size mismatch for {dest.name}: got {final_size}, "
            f"expected {expected}. The download was interrupted or the "
            f"remote file changed. Delete {tmp} and retry."
        )
    tmp.replace(dest)


def _write(resp, tmp: Path, start: int, expected: int) -> None:
    mode = "ab" if start else "wb"
    downloaded = start
    last_pct = -5
    chunk = 1024 * 1024 * 4
    with open(tmp, mode) as fh:
        for data in resp.iter_content(chunk_size=chunk):
            if not data:
                continue
            fh.write(data)
            downloaded += len(data)
            if expected:
                pct = int(downloaded * 100 / expected)
                if pct >= last_pct + 5:
                    c.info(
                        f"  {pct:3d}%  "
                        f"{c.human_size(downloaded)} / {c.human_size(expected)}"
                    )
                    last_pct = pct


def fetch_one(key: str, entry: Dict, settings: Dict) -> None:
    expected = int(entry.get("size", 0))
    local = dest_path(entry, settings)
    url = resolve_url(entry)

    if correct_size(local, expected):
        c.ok(f"{entry['filename']} present ({c.human_size(expected)}).")
        return

    # Try Drive cache first.
    cache = drive_cache_path(entry, settings)
    if cache and correct_size(cache, expected):
        c.step(f"Copying {entry['filename']} from Google Drive cache")
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache, local)
        c.ok(f"Restored {entry['filename']} from Drive.")
        return

    c.step(f"Downloading {entry['filename']}  ({c.human_size(expected)})")
    if entry.get("gated"):
        c.info("This is a gated model; set HF_TOKEN if you get a 401/403.")
    stream_download(url, local, expected)
    c.ok(f"Downloaded {entry['filename']}.")

    # Mirror to Drive cache.
    if cache:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, cache)
            c.info(f"Mirrored to Drive cache: {cache}")
        except OSError as exc:
            c.warn(f"Could not mirror to Drive ({exc}).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", action="append", default=[],
                    help="tier(s) to download (default: settings tier)")
    ap.add_argument("--list", action="store_true", help="list and exit")
    ap.add_argument("--verify-urls", action="store_true",
                    help="HEAD-check all URLs/sizes without downloading")
    args = ap.parse_args()

    settings = c.load_settings()
    models_cfg = c.load_models()

    if args.verify_urls:
        return verify_urls(models_cfg)

    tiers = args.tier or [c.selected_tier(settings)]
    keys: List[str] = []
    for t in tiers:
        for k in tier_models(models_cfg, t):
            if k not in keys:
                keys.append(k)

    entries = models_cfg["models"]
    total = sum(int(entries[k].get("size", 0)) for k in keys)
    c.step(f"Tier(s) {tiers}: {len(keys)} file(s), ~{c.human_size(total)} total")

    if args.list:
        for k in keys:
            e = entries[k]
            print(f"  {k:20s} {e['dest']:16s} {e['filename']}  "
                  f"({c.human_size(int(e.get('size', 0)))})")
        return 0

    for k in keys:
        fetch_one(k, entries[k], settings)

    c.ok(f"All models for tier(s) {tiers} are present.")
    return 0


def verify_urls(models_cfg: Dict) -> int:
    bad = 0
    for key, entry in models_cfg["models"].items():
        url = resolve_url(entry)
        size = head_size(url)
        expected = int(entry.get("size", 0))
        if size is None:
            c.error(f"{key}: could not resolve size for {url}")
            bad += 1
        elif expected and size != expected:
            c.warn(f"{key}: remote size {size} != manifest {expected} ({url})")
            bad += 1
        else:
            c.ok(f"{key}: {c.human_size(size)}  OK")
    if bad:
        c.error(f"{bad} URL check(s) had problems.")
        return 1
    c.ok("All model URLs verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
