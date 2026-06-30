"""OpenAI LLM adapter.

Authentication: Authorization: Bearer <api_key>.
Endpoint: https://api.openai.com/v1/chat/completions

Model routing is via the request body's 'model' field. The model_hint maps to
a model name stored at construction time; if no hint matches, the default model
is used.
"""

from __future__ import annotations

import os

import httpx
from iris_adapter_llm_shared import OpenAICompatProvider, RetryConfig

_DEFAULT_MODEL = "gpt-4o-mini"
_BASE_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(OpenAICompatProvider):
    """LLM adapter for OpenAI API."""

    version: str = "1.0.0"

    @property
    def id(self) -> str:
        return "openai"

    def __init__(
        self,
        api_key: str,
        model_chat: str = _DEFAULT_MODEL,
        model_extract: str = _DEFAULT_MODEL,
        *,
        retry_config: RetryConfig | None = None,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config, _http_client=_http_client)
        self._api_key = api_key
        self._model_chat = model_chat
        self._model_extract = model_extract

    @classmethod
    def from_env(cls, retry_config: RetryConfig | None = None) -> OpenAIProvider:
        """Construct from environment variables.

        Required:
            IRIS_LLM_OPENAI_API_KEY    OpenAI API key

        Optional:
            IRIS_LLM_OPENAI_MODEL_CHAT     Model for chat/classify/summarise (default: gpt-4o-mini)
            IRIS_LLM_OPENAI_MODEL_EXTRACT  Model for extraction calls (default: gpt-4o-mini)
        """
        return cls(
            api_key=_require_env("IRIS_LLM_OPENAI_API_KEY"),
            model_chat=os.environ.get("IRIS_LLM_OPENAI_MODEL_CHAT", _DEFAULT_MODEL),
            model_extract=os.environ.get("IRIS_LLM_OPENAI_MODEL_EXTRACT", _DEFAULT_MODEL),
            retry_config=retry_config,
        )

    def _base_url(self) -> str:
        return _BASE_URL

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _model_for_hint(self, hint: str | None, default: str) -> str:
        if hint == "extraction":
            return self._model_extract
        return self._model_chat


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return value
