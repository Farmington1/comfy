# AI Video Studio

A portable, GitHub-hosted **AI video-generation studio** that runs **ComfyUI**
and **Wan 2.2** video models on **Google Colab**. Clone it, open the notebook in
Colab, run the cells, and generate text-to-video and image-to-video clips - no
local GPU, CUDA, PyTorch or ComfyUI install required on your laptop.

> **Open in Colab**
>
> [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Farmington1/comfy/blob/main/colab/ComfyUI_Video_Generation.ipynb)
>
> The badge works only with a **public github.com** copy of this repo. If you
> host it on an enterprise/private Git server, mirror it to github.com (or
> upload `colab/ComfyUI_Video_Generation.ipynb` directly to Colab) and update
> the link above and `AVS_REPO_URL`.

---

## What it does

- **Text-to-video** and **image-to-video** with **Wan 2.2** (the latest open
  Wan weights; see the note on "Wan 3.0" below).
- Automatic, **pinned, reproducible** install of ComfyUI + dependencies.
- **Automatic model downloads** (only what the chosen tier needs), with resume
  and Google Drive caching.
- **Four ready-to-use workflows**: text-to-video, image-to-video, fast preview,
  high quality.
- **Persistent Google Drive storage** for models, inputs and generated videos.
- GPU detection, VRAM/CUDA/RAM/disk checks and clear, actionable warnings.
- **MP4 export** via FFmpeg (bundled in Colab).

## Supported models

| Tier | Model(s) | Workflows | Approx. download |
|------|----------|-----------|------------------|
| `base` (default) | Wan 2.2 **TI2V 5B** + UMT5 encoder + Wan 2.2 VAE | `wan_text_to_video`, `wan_image_to_video`, `fast_preview` | ~17 GB |
| `quality` | Wan 2.2 **14B Text-to-Video** (high+low noise, fp8) + VAE | `high_quality` | ~35 GB |
| `i2v_14b` | Wan 2.2 **14B Image-to-Video** (high+low noise, fp8) | custom | ~35 GB |
| `gguf` | Quantized 14B T2V (Q4_K_M) for low VRAM | custom | ~20 GB |

All Wan 2.2 weights are redistributed by Comfy-Org under **Apache-2.0** and are
public (no Hugging Face token required). See [docs/MODELS.md](docs/MODELS.md).

> **Is there a "Wan 3.0"?** Not as downloadable weights. "Wan 2.6 / 2.7 / 3.0"
> exist only as Alibaba **cloud API** models (ComfyUI "API nodes", paid). The
> newest model you can download and run locally in ComfyUI is **Wan 2.2**, which
> this project uses.

## Hardware requirements

Everything GPU-related runs **in Colab**, not on your laptop.

| GPU (Colab) | VRAM | Recommended |
|-------------|------|-------------|
| A100 | 40 / 80 GB | `quality` tier, `high_quality` workflow |
| L4 | 24 GB | `base` tier, `wan_text_to_video` |
| T4 | 16 GB | `base` tier + `--lowvram`, `fast_preview` |
| smaller | < 16 GB | `gguf` tier + `fast_preview` |

## Quick start

1. Open the notebook with the **Open in Colab** badge above (or upload
   `colab/ComfyUI_Video_Generation.ipynb` to [colab.research.google.com](https://colab.research.google.com)).
2. `Runtime -> Change runtime type -> GPU`.
3. In the first cell, set `REPO_URL` to your public repo clone URL.
4. Run the cells top to bottom:
   - validate the environment,
   - (optionally) mount Google Drive,
   - install ComfyUI + download models (`Step 3`),
   - generate a video (`Step 5`).

Full walkthrough: [docs/QUICK_START.md](docs/QUICK_START.md).

## Where videos are saved

- Locally on the Colab VM: `ComfyUI/output/AI-Video-Studio/...`
- Persisted to Google Drive: `MyDrive/AI-Video-Studio/outputs/`
- The notebook also offers a direct browser download of each clip.

## Compliance with Google Colab's terms

The **free** Colab tier disallows "bypassing the notebook UI to interact
primarily via a web UI". This project therefore runs ComfyUI **headless on
localhost** and submits workflows through its **local API from notebook cells** -
a compliant, notebook-driven path. Exposing the real ComfyUI web interface via a
public tunnel (ngrok/cloudflared) is **only** appropriate on a **paid** Colab
plan. This repo never opens a tunnel automatically.

## Updating the environment

Versions are pinned in `config/settings.yaml` (ComfyUI tag),
`config/custom_nodes.yaml` (node commits) and `config/models.yaml` (exact model
files + sizes). To update, bump the pin and re-run the setup cell - installs are
idempotent and will not clobber your workflows or outputs. See
[docs/QUICK_START.md](docs/QUICK_START.md#updating).

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for GPU, VRAM, download,
and runtime-disconnect issues.

## Repository layout

```
.
├── colab/ComfyUI_Video_Generation.ipynb   # the one notebook you run
├── scripts/                               # install / download / launch / generate
├── config/                                # pinned settings, models, custom nodes
├── workflows/                             # 4 ComfyUI API-format workflows
├── docs/                                  # quick start, models, troubleshooting
└── tests/                                 # config / workflow / install validation
```

## License

Project code: MIT (see repository). Model weights retain their own licenses
(Wan 2.2: Apache-2.0) - review before commercial use.
