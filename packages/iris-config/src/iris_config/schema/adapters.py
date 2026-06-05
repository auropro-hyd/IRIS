"""AdaptersSchema: adapter selection for a Product bundle.

The Literal types enumerate every adapter shipped by workstreams 003 and 004.
Adding a fifth adapter requires updating the Literal here.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

OcrAdapter = Literal["adi", "datalab", "paddleocr", "local"]
LlmAdapter = Literal["azure-openai", "openai", "anthropic", "local"]


class AdaptersSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr: OcrAdapter
    llm: LlmAdapter
