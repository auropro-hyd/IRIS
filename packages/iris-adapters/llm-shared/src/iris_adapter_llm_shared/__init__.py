"""iris-adapter-llm-shared: internal base classes shared by OpenAI-compatible LLM adapters.

Not published. Consumed only by iris-adapter-llm-azure-openai, iris-adapter-llm-openai,
and iris-adapter-llm-local. iris-adapter-llm-anthropic has a standalone implementation.
"""

from iris_adapter_llm_shared.env import require_env
from iris_adapter_llm_shared.openai_compat import OpenAICompatProvider
from iris_adapter_llm_shared.retry import RetryConfig, with_retry

__all__ = [
    "OpenAICompatProvider",
    "RetryConfig",
    "require_env",
    "with_retry",
]
