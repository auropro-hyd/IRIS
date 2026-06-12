# iris-ocr-local

Tesseract OCR adapter for IRIS. Wraps `pytesseract` to run Tesseract entirely on-device. No external API calls; no model download required.

## Prerequisites

### System binary (required)

`pytesseract` is a Python wrapper around the `tesseract` binary. The binary must be installed at the OS level - it cannot be installed through `uv` or `pip`.

**Ubuntu / Debian:**

```
sudo apt install tesseract-ocr tesseract-ocr-eng
```

**macOS:**

```
brew install tesseract
```

**Windows (Chocolatey):**

```
choco install tesseract
```

**Windows (winget):**

```
winget install tesseract-ocr.tesseract-ocr
```

On Windows, Tesseract installs to `C:\Program Files\Tesseract-OCR\` and may not be on `PATH`. If `pytesseract` cannot find the binary, set `IRIS_TESSERACT_CMD` (see below).

### Python packages

Installed automatically by `make install`:

- `pytesseract>=0.3.10` - Python wrapper around the Tesseract binary
- `pymupdf>=1.24` - PDF rasterisation
- `iris-engine` - workspace contract types

### Additional language packs

Tesseract defaults to English (`eng`). For other languages install the system pack and pass the language code:

```
# Ubuntu example - French + German
sudo apt install tesseract-ocr-fra tesseract-ocr-deu
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `IRIS_TESSERACT_CMD` | No | Full path to the `tesseract` binary. Useful on Windows or custom installs where the binary is not on `PATH` |
| `IRIS_OCR_LIVE_LOCAL` | No | Set to `1` to enable the live integration test |

## Running tests

Unit tests (tesseract binary is mocked, no system dependency needed):

```
uv run pytest packages/iris-adapters/ocr-local/tests/test_unit.py
```

Live integration test (calls the real tesseract binary):

```
IRIS_OCR_LIVE_LOCAL=1 uv run pytest -m slow packages/iris-adapters/ocr-local/tests/test_live.py
```

Requires `tesseract-ocr` installed on the system.

## How it works

1. `extract()` rasterises each PDF page to a PIL Image at 150 DPI via PyMuPDF.
2. Each image is passed to `pytesseract.image_to_data()` which returns per-word text, bounding boxes, and confidence scores.
3. Words with `conf >= 0` and non-empty text are kept. Blocks are grouped by Tesseract's block number and joined with `\n\n`.
4. Confidence per page is the mean of per-word scores normalised from 0-100 to 0.0-1.0. Pages with no detected words return `confidence=0.0`.

## Limitations

- Quality depends heavily on image resolution and scan quality. 150 DPI is the default; dense or small text may require 300 DPI.
- Only English (`eng`) is enabled by default. Multi-language documents require additional system packs.
- Tesseract has no GPU acceleration. Inference is CPU-only and scales linearly with page count and resolution.
- `make distclean` does not uninstall the `tesseract-ocr` system binary. To remove it manually: `sudo apt remove tesseract-ocr` (Linux) or `brew uninstall tesseract` (macOS).
