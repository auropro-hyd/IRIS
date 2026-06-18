"""AdaptersSchema: adapter selection for a Product bundle.

The Literal types enumerate every adapter shipped by workstreams 003 and 004.
Adding a fifth adapter requires updating the Literal here AND regenerating the
JSON schema used for IDE validation:

    iris config schema product -o docs/schemas/product.schema.json

OcrParams and LlmParams were specified in the WS003 and WS004 plan.md files as
"consumed from workstream 002" but were never added to this schema during those
workstreams. They are added here in T043 to close that gap.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OcrAdapter = Literal["adi", "datalab", "paddleocr", "local"]
LlmAdapter = Literal["azure-openai", "openai", "anthropic", "local"]


class OcrParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    languages: list[str] = Field(default_factory=lambda: ["en"])


class LlmParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_chat: str = "gpt-4o-mini"
    model_extract: str = "gpt-4o-mini"
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_ms: int = Field(default=500, ge=0)


class AdaptersSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr: OcrAdapter
    llm: LlmAdapter
    ocr_fallback: OcrAdapter | None = None
    llm_fallback: LlmAdapter | None = None
    ocr_params: OcrParams = Field(default_factory=OcrParams)
    llm_params: LlmParams = Field(default_factory=LlmParams)
