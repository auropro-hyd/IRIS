# iris-ocr-datalab

Datalab OCR adapter for IRIS. Calls the Datalab convert API using `httpx.AsyncClient`.

## Prerequisites

- A Datalab account and API key from [datalab.to](https://www.datalab.to).

### Python packages

Installed automatically by `make install`:

- `httpx>=0.27` - async HTTP client
- `iris-engine` - workspace contract types

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATALAB_API_KEY` | Yes | API key from your Datalab account |
| `IRIS_OCR_LIVE_DATALAB` | No | Set to `1` to enable the live integration test |

Copy `.env.example` to `.env` and fill in the Datalab values.

## Running tests

Unit tests (no network, fully mocked):

```
uv run pytest packages/iris-adapters/ocr-datalab/tests/test_unit.py
```

Live integration test (hits the real Datalab endpoint):

```
uv run --env-file .env pytest -m slow packages/iris-adapters/ocr-datalab/tests/test_live.py
```

Requires `DATALAB_API_KEY` and `IRIS_OCR_LIVE_DATALAB=1` in `.env`.

## How it works

1. `extract()` POSTs the document bytes to `/api/v1/convert`.
2. Datalab returns `{"success": true, "request_check_url": "..."}`.
3. The adapter polls the check URL every 3 s until `status == "complete"` or the 300 s deadline is reached.
4. The markdown string (all pages joined by `\n\n---\n\n`) is split by that separator and aligned to the `page_count` from the response.

## Limitations

- Bboxes are always empty (`[]`). The Datalab convert endpoint returns markdown only; it does not return per-word polygon coordinates.
- Confidence is sourced from `parse_quality_score` in the Datalab response. If the field is absent it defaults to `0.0`.
- Rate limiting (HTTP 429 / 529) raises `OCRRateLimited`; callers should back off and retry.
