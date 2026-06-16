# iris-ocr-paddleocr

PaddleOCR-VL-1.6 local OCR adapter for IRIS. Runs a 1B vision-language model entirely on-device using the `paddleocr` library. No external API calls in production.

## Prerequisites

### Python packages

Installed automatically by `make install` (via `uv sync`):

- `paddlepaddle>=3.1` - PaddlePaddle inference engine (CPU build)
- `paddleocr[doc-parser]>=3.6.0` - PaddleOCR library and document pipeline
- `pymupdf>=1.24` - PDF rasterisation
- `huggingface_hub>=0.23` - model snapshot download

### GPU support (optional but strongly recommended)

CPU inference is approximately 7-8 minutes per page. GPU inference (CUDA) is approximately 10-30 seconds per page.

The GPU wheel is not on PyPI. After `make install`, replace the CPU build with the GPU build:

```
pip install paddlepaddle-gpu==3.2.1 \
    --index-url https://www.paddlepaddle.org.cn/packages/stable/cu123/
```

CUDA 12.3 is required. For other CUDA versions see [PaddlePaddle installation](https://www.paddlepaddle.org.cn/install/quick).

### Model download

The model (~1.8 GB) must be downloaded before first use. Run once:

```
uv run python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='PaddlePaddle/PaddleOCR-VL-1.6', local_dir='PaddleOCR-VL-1.6-snapshot')
"
```

Then set in `.env`:

```
IRIS_PADDLEOCR_OFFLINE=1
IRIS_PADDLEOCR_MODEL_PATH=PaddleOCR-VL-1.6-snapshot
```

In online mode (no env vars set), the model downloads automatically to `~/.paddlex/official_models/PaddleOCR-VL-1.6/` on first use.

### Fully airgapped deployment

`IRIS_PADDLEOCR_OFFLINE=1` blocks HuggingFace calls for the VL recognition model but does **not** block PaddlePaddle's CDN. The pipeline uses two additional models that auto-download on first use:

- `PP-DocLayoutV3` - layout detection, fetched from PaddlePaddle's CDN via ModelScope
- doc-preprocessor sub-model (image normalisation), same source

Both land under `~/.paddlex/official_models/` when first run with network access.

**Step 1 - pre-seed on a networked machine (run once):**

```bash
# Download the VL recognition model from HuggingFace
uv run python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='PaddlePaddle/PaddleOCR-VL-1.6', local_dir='PaddleOCR-VL-1.6-snapshot')
"

# Trigger sub-model downloads by running inference once
IRIS_PADDLEOCR_OFFLINE=1 IRIS_PADDLEOCR_MODEL_PATH=PaddleOCR-VL-1.6-snapshot \
  IRIS_OCR_LIVE_PADDLEOCR=1 uv run pytest -m slow \
  packages/iris-adapters/ocr-paddleocr/tests/test_live.py
# PP-DocLayoutV3 and doc-preprocessor now cached in ~/.paddlex/official_models/
```

**Step 2 - transfer caches to the airgapped host:**

```bash
rsync -a PaddleOCR-VL-1.6-snapshot/   airgapped-host:/opt/iris/models/PaddleOCR-VL-1.6-snapshot/
rsync -a ~/.paddlex/official_models/   airgapped-host:/opt/iris/paddlex-models/official_models/
```

**Step 3 - set env vars on the airgapped host:**

```bash
export IRIS_PADDLEOCR_OFFLINE=1
export IRIS_PADDLEOCR_MODEL_PATH=/opt/iris/models/PaddleOCR-VL-1.6-snapshot
export PADDLEX_HOME=/opt/iris/paddlex-models   # PaddleX looks for official_models/ here
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True  # skip ModelScope connectivity check at startup
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

If `PADDLEX_HOME` is not set, PaddleX defaults to `~/.paddlex/`; transfer the `official_models/` directory there instead.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `IRIS_PADDLEOCR_OFFLINE` | No | Set to `1` to load from a local snapshot instead of HuggingFace |
| `IRIS_PADDLEOCR_MODEL_PATH` | If OFFLINE=1 | Path to the local HF snapshot directory |
| `PADDLEX_HOME` | No | Root directory for the PaddleX model cache. Set on airgapped hosts to redirect PP-DocLayoutV3 and sub-model storage (see Fully airgapped deployment above) |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | No | Set to `True` to skip ModelScope connectivity checks at startup. Required on airgapped hosts where ModelScope is unreachable |
| `TRANSFORMERS_OFFLINE` | No | Set to `1` to block all HuggingFace network calls |
| `HF_DATASETS_OFFLINE` | No | Set to `1` to block HuggingFace dataset calls |
| `IRIS_OCR_LIVE_PADDLEOCR` | No | Set to `1` to enable the live integration test |

## Running tests

Unit tests (no model, fully mocked):

```
uv run pytest packages/iris-adapters/ocr-paddleocr/tests/test_unit.py
```

Live integration test (loads the real model):

```
uv run --env-file .env pytest -m slow packages/iris-adapters/ocr-paddleocr/tests/test_live.py
```

Requires the model to be downloaded and `IRIS_OCR_LIVE_PADDLEOCR=1` in `.env`. Expect 900-1000 s on (model load and inference for a real document - 2 pages).

## How it works

1. `extract()` rasterises each PDF page to a PIL Image at 150 DPI via PyMuPDF.
2. Each image is passed to `PaddleOCRVL.predict()` as a numpy array.
3. The result (`PaddleOCRVLResult`) exposes `result["parsing_res_list"]` - a list of `PaddleOCRVLBlock` objects with `.bbox` (`[x1, y1, x2, y2]` integers) and `.content` (text string).
4. Blocks are joined with `\n\n` to produce the page markdown.

## Limitations

- Confidence is always `1.0`. The VLM backbone does not produce a per-block confidence score.
- `IRIS_PADDLEOCR_OFFLINE=1` prevents HuggingFace calls but does not prevent PaddlePaddle CDN calls. PP-DocLayoutV3 and the doc-preprocessor sub-model auto-download from that CDN on first use. For a fully airgapped environment, pre-seed those sub-models and set `PADDLEX_HOME` to redirect the cache; see Fully airgapped deployment above.
- CPU inference is too slow for production use.
