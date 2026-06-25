"""iris-llm-shared: internal base classes shared by OpenAI-compatible LLM adapters.

Not published. Consumed only by iris-llm-azure-openai, iris-llm-openai,
and iris-llm-local. iris-llm-anthropic has a standalone implementation.
"""

from iris_adapter_llm_shared.openai_compat import OpenAICompatProvider
from iris_adapter_llm_shared.retry import RetryConfig, with_retry

__all__ = [
    "OpenAICompatProvider",
    "RetryConfig",
    "with_retry",
]
