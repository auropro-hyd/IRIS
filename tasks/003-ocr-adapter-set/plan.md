# Plan 003: OCR Adapter Set

**Workstream**: `003-ocr-adapter-set`
**Status**: Draft
**Specification**: [spec.md](./spec.md)  -  **Contract**: [contracts/ocr-engine.md](./contracts/ocr-engine.md)

## Approach

The `OCREngine` Protocol lives in `iris-engine`. The four adapters are independent packages so a deployment can install only what it needs. A small selector in `iris-engine` reads the Product's `adapters.ocr` value and returns the configured `OCREngine` instance, with optional fallback to a second adapter if configured.

PaddleOCR-from-HuggingFace and the local Tesseract adapter share the "no outbound network" property. They are kept as separate adapters because their model artefacts and runtime characteristics differ: PaddleOCR ships from Hugging Face and runs on PyTorch; Tesseract ships from `apt` and runs on CPU.

## Proposed file layout

```
packages/iris-engine/src/iris_engine/contracts/
└── ocr_engine.py              # OCREngine Protocol + result types + error types

packages/iris-engine/src/iris_engine/ocr/
├── __init__.py                # OCREngine, select_ocr_engine()
├── selector.py                # reads adapters.ocr from ProductConfig
└── in_memory.py               # InMemoryOCREngine (for tests, returns canned results)

packages/iris-adapters/ocr-adi/
├── pyproject.toml
└── src/iris_adapter_ocr_adi/
    ├── __init__.py            # AdiOCREngine
    └── client.py              # Azure Document Intelligence client wiring

packages/iris-adapters/ocr-datalab/
├── pyproject.toml
└── src/iris_adapter_ocr_datalab/
    ├── __init__.py            # DatalabOCREngine
    └── client.py              # Datalab API client

packages/iris-adapters/ocr-paddleocr/
├── pyproject.toml             # depends on transformers, torch, paddleocr (HF version)
└── src/iris_adapter_ocr_paddleocr/
    ├── __init__.py            # PaddleOCREngine
    └── model.py               # model loading, GPU detection

packages/iris-adapters/ocr-local/
├── pyproject.toml             # depends on pytesseract; CPU-only by default
└── src/iris_adapter_ocr_local/
    ├── __init__.py            # LocalOCREngine
    └── tesseract.py           # Tesseract wrapper

tests/contract/
└── test_ocr_contract.py       # parametrised over registered adapters

packages/iris-adapters/ocr-*/tests/
├── test_unit.py               # adapter-specific unit tests with mocked external calls
└── test_live.py               # gated on IRIS_OCR_LIVE_<NAME>=1
```

## Key choices

1. **Protocol in `iris-engine`, implementations in `iris-adapters`**. The engine never imports an adapter.
2. **PaddleOCR via the Hugging Face transformer port**. Specifically, `paddleocr` with `cls_image_shape` set; model is downloaded once at startup and cached in the image.
3. **ADI authentication via API key initially**. Token-based auth (Entra) lands when the OIDC workstream is in motion.
4. **Datalab uses async HTTP** through `httpx.AsyncClient` with retry on `429`.
5. **Local adapter ships Tesseract**. PaddleOCR-local is a separate variant tracked under the `paddleocr` adapter (with `IRIS_PADDLEOCR_OFFLINE=1`).
6. **Fallback is opt-in via Product config**. `adapters.ocr_fallback: local` is a separate field; default is no fallback.

## Configuration shape (consumed from workstream 002)

```yaml
# config/products/commercial-auto-claims/in/product.yaml
adapters:
  ocr: paddleocr            # one of: adi | datalab | paddleocr | local
  ocr_fallback: local       # optional, same set
  ocr_params:
    confidence_threshold: 0.6
    languages: [en, hi]
```

## Out of scope

- A scoring framework that picks the best adapter per document type. That belongs in a later "OCR routing" workstream.
- Streaming OCR (page-by-page as soon as each page is ready). Single-call extraction returns the whole document.
- An OCR-side fraud or risk signal. The fraud workstream is later.

## Dependencies

- Workstream 001 (scaffold).
- Workstream 002 (configuration framework) for the adapter selection.
