# Troubleshooting

Each setup/generation step prints an actionable message on failure. Common
issues and fixes:

## No GPU / "No NVIDIA GPU detected"
`Runtime -> Change runtime type -> Hardware accelerator -> GPU`, then
`Runtime -> Reconnect`. Re-run the validation cell. Free Colab GPUs are not
guaranteed and may be unavailable at peak times; try later or use a paid plan.

## "CUDA not available to PyTorch"
Usually means the runtime connected without a GPU, or a package reinstalled a
CPU-only torch. Do **not** `pip install torch` yourself - Colab ships the right
CUDA build and `install_comfyui.py` deliberately keeps it. Reset the runtime
(`Runtime -> Disconnect and delete runtime`) and start over.

## Out of memory (OOM) during generation
- Use a smaller workflow: `fast_preview` (480p, short) or the `base` 5B model.
- Lower `width`/`height` and `length` in the `params` dict.
- Restart with the low-VRAM flag: re-run setup; `validate_environment` adds
  `--lowvram` automatically for <16 GB GPUs. You can force it:
  `!python scripts/launch_comfyui.py stop && python scripts/launch_comfyui.py start --vram-flag --lowvram`
- For very small GPUs, use the `gguf` tier (see [MODELS.md](MODELS.md)).

## Download is slow or interrupted
Downloads **resume** automatically - just re-run Step 3 (or
`python scripts/download_models.py --tier base`). Integrity is checked by file
size; a mismatched/partial file is re-fetched. If Google Drive caching is on, a
previously downloaded file is restored from Drive instead of re-downloaded.

## "ComfyUI did not become ready" / server won't start
The launcher prints the tail of the server log. Common causes:
- A model file failed to download (run Step 3 again).
- Not enough disk (`base` needs ~17 GB, `quality` ~35 GB). Check the disk line
  in the validation cell; free space or disable Drive mirroring.
- A custom node failed to import. The core workflows need no custom nodes, so
  try `TIER = 'base'`.
Full log: `/content/ai-video-studio-logs/comfyui.log`.

## "Workflow validation errors" / missing model
Means a node references a model file that isn't present. Ensure the tier that
provides it was downloaded (e.g. `high_quality` needs `TIER = 'quality'`). Run:
`python scripts/download_models.py --tier quality --list` to see expected files.

## Google Drive mount fails
Approve the authorization popup. If it keeps failing, set `USE_DRIVE = False`
to run ephemerally (outputs stay on the Colab VM only) and re-run.

## Runtime disconnected / lost everything
Colab recycles free runtimes after idle timeouts or long sessions. With Google
Drive enabled, your **models and videos are safe** in `MyDrive/AI-Video-Studio/`.
Reconnect, re-run Steps 1-4; cached models are restored from Drive rather than
re-downloaded.

## I want the real ComfyUI web UI
Only do this on a **paid** Colab plan with a positive compute-unit balance -
exposing a web UI on the free tier violates Colab's terms. You would start the
server and open a tunnel yourself; this repo intentionally does not automate it.

## Shutting down to save compute units
Run the stop cell, then `Runtime -> Disconnect and delete runtime`. Do **not**
leave an idle GPU runtime connected. This project never purchases compute units
or starts paid services for you.
