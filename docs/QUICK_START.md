# Quick Start (for people new to ComfyUI)

This guide gets you from zero to a generated video. You do **not** need to know
ComfyUI - the notebook drives everything for you.

## 0. What you need

- A Google account.
- A web browser.
- (That's it. No GPU, CUDA, PyTorch or ComfyUI on your laptop.)

## 1. Open the notebook in Colab

Either:

- Click the **Open in Colab** badge in the [README](../README.md), **or**
- Go to [colab.research.google.com](https://colab.research.google.com),
  choose `File -> Upload notebook`, and upload
  `colab/ComfyUI_Video_Generation.ipynb`.

> Colab's "open from GitHub" feature only works with **public github.com**
> repositories. If this project lives on a private/enterprise Git host, either
> mirror it to github.com or just upload the `.ipynb` as above.

## 2. Turn on the GPU

`Runtime -> Change runtime type -> Hardware accelerator -> GPU -> Save`, then
`Connect`.

- Best: **A100** (40 or 80 GB). Needs Colab Pro/Pro+ or pay-as-you-go.
- Works: **L4** (24 GB) or **T4** (16 GB) with the smaller model.

## 3. Run the cells in order

### Step 1 - Load the project & check the GPU
Set `REPO_URL` (first code cell) to your repo's public clone URL, then run it.
It clones the repo and prints your GPU. The next cell runs a full environment
check and tells you which **tier** your GPU can handle.

### Step 2 - Mount Google Drive (recommended)
Approve the Google authorization popup. Your models and videos will persist in
`MyDrive/AI-Video-Studio/` across sessions. (Set `USE_DRIVE = False` to skip.)

### Step 3 - Install & download
Leave `TIER = 'auto'` to use the recommendation, or set it explicitly:
- `'base'` - Wan 2.2 **5B** model. Smallest download, powers text-to-video,
  image-to-video and fast preview. **Best choice for your first run.**
- `'quality'` - Wan 2.2 **14B** model for the `high_quality` workflow (large
  download, needs a big GPU).

This cell installs ComfyUI (pinned version), downloads only the models the tier
needs, and starts ComfyUI in the background. It is safe to re-run; it skips work
that is already done and resumes interrupted downloads.

### Step 4 - Confirm it's ready
You should see `ComfyUI UP` with your GPU's VRAM.

### Step 5 - Generate your first video
Edit the `positive_prompt`, pick a `WORKFLOW`, and run. For the quickest result
use `WORKFLOW = 'fast_preview'`. The finished MP4 is shown inline, saved to
`ComfyUI/output/AI-Video-Studio/`, and copied to Google Drive.

### Step 6 - Image-to-video (optional)
Upload an image, add a motion prompt, and run.

### Step 7 - Shut down
Run the stop cell, then `Runtime -> Disconnect and delete runtime` to stop
consuming compute units. Your Drive files are kept.

## The four workflows

| Workflow | Model | Good for |
|----------|-------|----------|
| `fast_preview` | Wan 2.2 5B | Quick idea tests (480p, ~2s, few steps) |
| `wan_text_to_video` | Wan 2.2 5B | Text-to-video (720p, ~5s) |
| `wan_image_to_video` | Wan 2.2 5B | Animating a reference image |
| `high_quality` | Wan 2.2 14B | Best quality (needs `quality` tier + big GPU) |

Change any setting by adding it to the `params` dict in Step 5, e.g.
`'length': 81`, `'steps': 20`, `'cfg': 5.0`, `'seed': 1234`.

> **Tip:** more steps is *not* always better. The defaults are tuned per
> workflow; raising steps mostly costs time.

## <a name="updating"></a>Updating the environment

All versions are pinned:

- **ComfyUI**: `config/settings.yaml` -> `comfyui.version`
- **Custom nodes**: `config/custom_nodes.yaml` -> `commit`
- **Models**: `config/models.yaml` -> exact filenames + sizes

To update, change the pin and re-run **Step 3**. Because installs are
idempotent and model integrity is checked by size, only the changed pieces are
re-fetched. Your edited workflows and generated videos in Drive are never
overwritten.

## Running the checks locally (no GPU needed)

```bash
pip install -r requirements.txt
pytest -q                       # config/workflow/structure validation
python scripts/download_models.py --verify-urls   # check model URLs are live
```
