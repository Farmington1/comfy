# Models

This project uses **Wan 2.2**, the latest Wan video model with downloadable
weights and native ComfyUI support. All files are redistributed by
[Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
(Apache-2.0, public, **no token required**).

## "Wan 3.0"?

There is **no downloadable Wan 3.0** (nor 2.6/2.7) at the time of writing. Those
version numbers exist only as **Alibaba cloud API** models, used in ComfyUI via
paid "API nodes" (`api_wan3_0_*` templates). The newest model you can download
and run locally is **Wan 2.2**, which this project uses.

## What each tier downloads

Exact files, destinations and sizes are pinned in `config/models.yaml`.

### `base` (default) - Wan 2.2 TI2V 5B
A single hybrid model that does **both** text-to-video and image-to-video.
Efficient (720p, 24fps, ~5s) and the fastest path to a first result.

| File | Folder | Size |
|------|--------|------|
| `wan2.2_ti2v_5B_fp16.safetensors` | `diffusion_models` | ~9.3 GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders` | ~6.3 GB |
| `wan2.2_vae.safetensors` | `vae` | ~1.3 GB |

Powers: `wan_text_to_video`, `wan_image_to_video`, `fast_preview`.

### `quality` - Wan 2.2 14B Text-to-Video (two-stage)
The 14B model uses the official two-stage sampling: a **high-noise** expert for
the first half of the steps and a **low-noise** expert for the second half
(`KSamplerAdvanced` with `start_at_step`/`end_at_step`). Highest quality;
needs a 24 GB+ GPU (comfortable on A100).

| File | Folder | Size |
|------|--------|------|
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | `diffusion_models` | ~14.3 GB |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | `diffusion_models` | ~14.3 GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders` | ~6.3 GB |
| `wan_2.1_vae.safetensors` | `vae` | ~0.25 GB |

Powers: `high_quality`.

### `i2v_14b` (optional) - Wan 2.2 14B Image-to-Video
Same two-stage structure as `quality`, tuned for image-to-video.

### `gguf` (optional, low VRAM)
Quantized Q4_K_M builds of the 14B T2V model from
[QuantStack](https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF)
(Apache-2.0). Requires the **ComfyUI-GGUF** custom node (installed automatically
when you select this tier). To use them, swap each `UNETLoader` in a workflow for
`UnetLoaderGGUF` and point it at the `.gguf` file. This path is for GPUs with
too little VRAM for the fp8 models; the default 5B model with `--lowvram`
already fits ~12 GB, so most users won't need GGUF.

## Key architecture notes (from the official ComfyUI Wan 2.2 docs)

- The **text encoder** is UMT5-XXL; `CLIPLoader` must use `type: wan`.
- The **5B** model uses `wan2.2_vae.safetensors`; the **14B** models use
  `wan_2.1_vae.safetensors`. Using the wrong VAE badly degrades quality.
- Wan 2.2 **does not** use `clip_vision` for image-to-video (unlike some older
  pipelines).
- The 5B latent node is `Wan22ImageToVideoLatent` (used for both t2v and i2v);
  the 14B t2v uses `EmptyHunyuanLatentVideo`.
- `length` (frame count) should be `4n + 1` (e.g. 49, 81, 121).

## Optional speed-up: Lightning LoRAs

`config/models.yaml` also defines the `speed_loras` tier (lightx2v 4-step
LoRAs). Applied to the 14B stages they let you generate in ~4 steps at `cfg 1.0`
(big speed-up, slight quality trade-off). They are not downloaded by default;
add them with `python scripts/download_models.py --tier speed_loras` and insert
a `LoraLoaderModelOnly` after each `UNETLoader`.

## Licensing

- **Wan 2.2** weights: Apache-2.0 (original: Wan-AI; repackaged by Comfy-Org).
- **UMT5** text encoder: Apache-2.0.
- Review the upstream model cards before any commercial use.
