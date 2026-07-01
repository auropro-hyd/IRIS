"""T053 acceptance: AgentError hierarchy is correctly typed and make typecheck is clean."""

from __future__ import annotations

import pytest
from iris_agents.errors import AgentError, AgentLLMError, AgentValidationError
from iris_engine.contracts.llm_provider import LLMError, LLMUnavailable


def test_agent_error_is_exception() -> None:
    with pytest.raises(AgentError):
        raise AgentError("base error")


def test_agent_llm_error_is_agent_error() -> None:
    cause = LLMUnavailable("service down")
    err = AgentLLMError("llm call failed", cause=cause)
    assert isinstance(err, AgentError)


def test_agent_llm_error_wraps_cause() -> None:
    cause = LLMUnavailable("timeout")
    err = AgentLLMError("llm call failed", cause=cause)
    assert err.cause is cause
    assert isinstance(err.cause, LLMError)
    assert str(err) == "llm call failed"


def test_agent_llm_error_cause_is_llm_error_subtype() -> None:
    cause = LLMUnavailable("503")
    err = AgentLLMError("unavailable", cause=cause)
    assert isinstance(err.cause, LLMUnavailable)


def test_agent_validation_error_is_agent_error() -> None:
    with pytest.raises(AgentError):
        raise AgentValidationError("required field missing")


def test_agent_validation_error_message() -> None:
    err = AgentValidationError("field 'incident_date' is required")
    assert "incident_date" in str(err)
