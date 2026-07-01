"""iris-agents error hierarchy.

AgentError is the base for all errors raised by iris-agents. AgentLLMError
wraps an LLMError from the adapter layer so callers can catch agent-level errors
without importing adapter types. AgentValidationError is raised when a structured
LLM response fails required-field validation.
"""

from __future__ import annotations

from iris_engine.contracts.llm_provider import LLMError


class AgentError(Exception):
    """Base for all iris-agents errors."""


class AgentLLMError(AgentError):
    """An LLM adapter call failed.

    Wraps the underlying LLMError so callers can catch AgentLLMError without
    importing the adapter's error hierarchy.
    """

    def __init__(self, message: str, cause: LLMError) -> None:
        super().__init__(message)
        self.cause: LLMError = cause
        self.__cause__ = cause


class AgentValidationError(AgentError):
    """A structured LLM response failed required-field validation.

    Raised by FieldExtractor when the LLM returns a response that does not
    satisfy the required fields declared in the Product's extraction schema.
    """
