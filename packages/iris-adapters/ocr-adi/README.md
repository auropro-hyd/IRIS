# iris-ocr-adi

Azure Document Intelligence (ADI) OCR adapter for IRIS. Calls the ADI REST API using `httpx.AsyncClient` (no Azure SDK dependency).

## Prerequisites

- An Azure subscription with a Document Intelligence resource provisioned.
- The resource endpoint and API key from the Azure portal.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `IRIS_ADI_ENDPOINT` | Yes | Full URL of your ADI resource (e.g. `https://my-resource.cognitiveservices.azure.com/`) |
| `IRIS_ADI_API_KEY` | Yes | API key from the Azure portal |
| `IRIS_ADI_MODEL` | No | ADI model to use. Defaults to `prebuilt-layout` |
| `IRIS_OCR_LIVE_ADI` | No | Set to `1` to enable the live integration test |

Copy `.env.example` to `.env` and fill in the ADI values.

## Running tests

Unit tests (no network, fully mocked):

```
uv run pytest packages/iris-adapters/ocr-adi/tests/test_unit.py
```

Live integration test (hits the real ADI endpoint):

```
uv run --env-file .env pytest -m slow packages/iris-adapters/ocr-adi/tests/test_live.py
```

Requires `IRIS_ADI_ENDPOINT`, `IRIS_ADI_API_KEY`, and `IRIS_OCR_LIVE_ADI=1` in `.env`.

## How it works

1. `extract()` POSTs the document bytes to `/documentModels/{model}:analyze`.
2. ADI returns HTTP 202 and an `Operation-Location` URL.
3. The adapter polls that URL every 1 s until `status == "succeeded"` or the 300 s deadline is reached.
4. The result is mapped to `OCRResult`: markdown from `content`, bboxes from ADI polygon coordinates (scaled from inches to pixels at 96 DPI), per-word confidence averaged per page.

## Limitations

- Token-based auth (Entra/OIDC) is not yet supported; only API key auth is wired.
- PDF page count is limited by the ADI model (prebuilt-layout supports up to 2000 pages).
- Bboxes are returned in pixels at 96 DPI (the standard screen approximation for inch-based ADI coordinates).
