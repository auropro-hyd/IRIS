"""Azure OpenAI LLM adapter.

Authentication: api-key header (not Bearer).
Endpoint: https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions
          with ?api-version={api_version} query param.

The deployment name acts as the model identifier on Azure. Two deployments are
supported - one for chat/classify/summarise calls and one for extraction calls.
Because the deployment is encoded in the URL (not the request body), a ContextVar
carries the active deployment into _base_url() so the base class HTTP machinery
picks the correct endpoint on each call.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

import httpx
from iris_adapter_llm_shared import OpenAICompatProvider, RetryConfig

_DEFAULT_API_VERSION = "2024-02-01"

# Set by _model_for_hint(), read by _base_url() - safe for concurrent asyncio tasks.
_active_deployment: ContextVar[str] = ContextVar("_azure_active_deployment", default="")


class AzureOpenAIProvider(OpenAICompatProvider):
    """LLM adapter for Azure OpenAI Service."""

    version: str = "1.0.0"

    @property
    def id(self) -> str:
        return "azure-openai"

    def __init__(
        self,
        resource: str,
        api_key: str,
        deployment_chat: str,
        deployment_extract: str,
        api_version: str = _DEFAULT_API_VERSION,
        *,
        retry_config: RetryConfig | None = None,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config, _http_client=_http_client)
        self._resource = resource.rstrip("/")
        self._api_key = api_key
        self._deployment_chat = deployment_chat
        self._deployment_extract = deployment_extract
        self._api_version = api_version

    @classmethod
    def from_env(cls, retry_config: RetryConfig | None = None) -> AzureOpenAIProvider:
        """Construct from environment variables.

        Required:
            IRIS_LLM_AZURE_RESOURCE            Azure resource name (subdomain only)
            IRIS_LLM_AZURE_API_KEY             API key
            IRIS_LLM_AZURE_DEPLOYMENT_CHAT     Deployment for chat/classify/summarise
            IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT  Deployment for extraction calls

        Optional:
            IRIS_LLM_AZURE_API_VERSION         Defaults to 2024-02-01
        """
        return cls(
            resource=_require_env("IRIS_LLM_AZURE_RESOURCE"),
            api_key=_require_env("IRIS_LLM_AZURE_API_KEY"),
            deployment_chat=_require_env("IRIS_LLM_AZURE_DEPLOYMENT_CHAT"),
            deployment_extract=_require_env("IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT"),
            api_version=os.environ.get("IRIS_LLM_AZURE_API_VERSION", _DEFAULT_API_VERSION),
            retry_config=retry_config,
        )

    def _base_url(self) -> str:
        deployment = _active_deployment.get(self._deployment_chat)
        return (
            f"https://{self._resource}.openai.azure.com"
            f"/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    def _auth_headers(self) -> dict[str, str]:
        return {"api-key": self._api_key}

    def _model_for_hint(self, hint: str | None, default: str) -> str:
        deployment = self._deployment_extract if hint == "extraction" else self._deployment_chat
        _active_deployment.set(deployment)
        return deployment


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return value
