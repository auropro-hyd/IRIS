"""Local LLM adapter.

Targets any OpenAI-compatible local inference server (vLLM, Ollama, llama.cpp).
Authentication: optional Bearer token (for servers that require one).
Endpoint: IRIS_LLM_LOCAL_URL (default http://localhost:8080/v1/chat/completions).

A single model is used for all hints; no chat/extract routing.
"""

from __future__ import annotations

import os

import httpx
from iris_adapter_llm_shared import OpenAICompatProvider, RetryConfig, require_env

_DEFAULT_BASE_URL = "http://localhost:8080/v1"


class LocalProvider(OpenAICompatProvider):
    """LLM adapter for a local OpenAI-compatible inference server."""

    version: str = "1.0.0"

    @property
    def id(self) -> str:
        return "local"

    def __init__(
        self,
        model: str,
        base_url: str = _DEFAULT_BASE_URL,
        api_key: str = "",
        *,
        retry_config: RetryConfig | None = None,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config, _http_client=_http_client)
        self._model = model
        self._base_url_str = base_url.rstrip("/")
        self._api_key = api_key

    @classmethod
    def from_env(cls, retry_config: RetryConfig | None = None) -> LocalProvider:
        """Construct from environment variables.

        Required:
            IRIS_LLM_LOCAL_MODEL    Model name served by the local endpoint

        Optional:
            IRIS_LLM_LOCAL_URL      Base URL (default: http://localhost:8080/v1)
            IRIS_LLM_LOCAL_API_KEY  Bearer token if the server requires auth
        """
        return cls(
            model=require_env("IRIS_LLM_LOCAL_MODEL"),
            base_url=os.environ.get("IRIS_LLM_LOCAL_URL", _DEFAULT_BASE_URL),
            api_key=os.environ.get("IRIS_LLM_LOCAL_API_KEY", ""),
            retry_config=retry_config,
        )

    def _base_url(self) -> str:
        return f"{self._base_url_str}/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _model_for_hint(self, hint: str | None, default: str) -> str:
        return self._model
