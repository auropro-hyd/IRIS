# iris-ocr-paddleocr

PaddleOCR-VL-1.6 local OCR adapter for IRIS. Runs a 1B vision-language model entirely on-device using the `paddleocr` library. No external API calls in production.

## Prerequisites

### Python packages

Installed automatically by `make install` (via `uv sync`):

- `paddleocr[doc-parser]>=3.6.0` - PaddleOCR library and document pipeline
- `pymupdf>=1.24` - PDF rasterisation
- `huggingface_hub>=0.23` - model snapshot download

### GPU support (optional but strongly recommended)

CPU inference is approximately 7-8 minutes per page. GPU inference (CUDA) is approximately 10-30 seconds per page.

The GPU wheel is not on PyPI and must be installed manually after `make install`:

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

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `IRIS_PADDLEOCR_OFFLINE` | No | Set to `1` to load from a local snapshot instead of HuggingFace |
| `IRIS_PADDLEOCR_MODEL_PATH` | If OFFLINE=1 | Path to the local HF snapshot directory |
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

Requires the model to be downloaded and `IRIS_OCR_LIVE_PADDLEOCR=1` in `.env`. Expect 15-30 s on first call (model load).

## How it works

1. `extract()` rasterises each PDF page to a PIL Image at 150 DPI via PyMuPDF.
2. Each image is passed to `PaddleOCRVL.predict()` as a numpy array.
3. The result (`PaddleOCRVLResult`) exposes `result["parsing_res_list"]` - a list of `PaddleOCRVLBlock` objects with `.bbox` (`[x1, y1, x2, y2]` integers) and `.content` (text string).
4. Blocks are joined with `\n\n` to produce the page markdown.

## Limitations

- Confidence is always `1.0`. The VLM backbone does not produce a per-block confidence score.
- `IRIS_PADDLEOCR_OFFLINE=1` prevents HuggingFace calls but does not prevent ModelScope calls. The PP-DocLayoutV3 sub-model auto-downloads from ModelScope on first use. For a fully airgapped environment, also stage PP-DocLayoutV3 locally and pass `layout_detection_model_dir` to `PaddleOCRVL`.
- CPU inference is too slow for production use. The production Docker image must include the GPU wheel.
