# AGENTS.md - guidance for AI agents working in this repo

## What this project is
A portable, GitHub-hosted environment that runs **ComfyUI + Wan 2.2** on
**Google Colab** to generate text-to-video and image-to-video clips. The laptop
is a thin client; all GPU work happens in Colab. The single entry point for
users is `colab/ComfyUI_Video_Generation.ipynb`.

## Golden rules
- **Keep it reproducible.** Every external dependency is pinned:
  ComfyUI tag in `config/settings.yaml`, custom-node commits in
  `config/custom_nodes.yaml`, exact model files + byte sizes in
  `config/models.yaml`. If you change a version, update the pin and say so.
- **Never commit large/binary/secret files.** No model weights
  (`*.safetensors`, `*.gguf`, ...), no generated media, no `.env`, no Drive
  credentials. `.gitignore` enforces this - don't weaken it.
- **Idempotency.** Install/download scripts must be safe to re-run and must not
  redo completed work or clobber user files (workflows, outputs).
- **Fail loudly, never silently skip** a critical setup step. Use the helpers
  in `scripts/common.py` (`step/info/ok/warn/error/fail`).
- **Colab ToS.** The free tier forbids interacting primarily via a web UI.
  The compliant path is: run ComfyUI headless on localhost and submit via its
  **local API** from notebook cells (`scripts/generate.py`). Do not add
  automatic ngrok/cloudflared tunnels.
- **Scope.** Build only what's in-scope (Colab + ComfyUI + Wan). Do **not** add
  AWS/K8s/Docker/web-app layers. Keep it modular for later, no premature
  abstraction.

## Layout & responsibilities
- `scripts/common.py` - config loading, paths, env overrides, logging. Reuse it.
- `scripts/setup.py` - orchestrates validate -> install -> nodes -> download ->
  drive -> launch. The notebook calls this.
- `scripts/validate_environment.py` - GPU/VRAM/CUDA/RAM/disk checks + tier rec.
- `scripts/install_comfyui.py` - pinned clone; keeps Colab's torch.
- `scripts/install_nodes.py` - optional custom nodes (none needed for core WFs).
- `scripts/download_models.py` - tiered, size-validated, resumable, Drive cache.
- `scripts/launch_comfyui.py` - headless localhost server (start/stop/status).
- `scripts/generate.py` - patch workflow params -> POST /prompt -> poll -> MP4.
- `scripts/sync_storage.py` - safe, non-destructive Google Drive sync.
- `workflows/*.json` - ComfyUI **API/prompt** format wrapped as
  `{ "name","description","tier","mode","meta","prompt" }`. `meta.params` maps a
  friendly param -> list of `[node_id, input_name]` to patch; `meta.defaults`
  holds defaults. Keep node ids and model filenames in sync with
  `config/models.yaml`.

## Workflow/model invariants (don't break these)
- `CLIPLoader` uses `type: wan` with `umt5_xxl_fp8_e4m3fn_scaled.safetensors`.
- 5B model -> `wan2.2_vae.safetensors`; 14B models -> `wan_2.1_vae.safetensors`.
- 5B latent node: `Wan22ImageToVideoLatent` (t2v omits `start_image`, i2v sets
  it). 14B t2v latent node: `EmptyHunyuanLatentVideo`.
- `length` must be `4n + 1`.
- Every model filename referenced by a workflow must exist as a model in
  `config/models.yaml` (tests enforce this).

## Before you commit
Run the checks (no GPU needed):
```bash
pip install -r requirements.txt
pytest -q
python scripts/download_models.py --verify-urls   # needs network
```
Do not claim a video was generated unless it was actually run on a GPU runtime.

## Meetings / decisions
If a change stems from a discussion, check Granola for context and note the
relevant decision in the PR description.
