"""iris-agents: DocumentClassifier and FieldExtractor for IRIS.

Result types: Classification, Extraction, FieldValidationError, MissingDocument.
Supporting result types: Citation, MissingDocuments, ExtractedField.
Errors: AgentError, AgentLLMError, AgentValidationError.
Template loading: TemplateLoader.
"""

from iris_agents.errors import AgentError, AgentLLMError, AgentValidationError
from iris_agents.results import (
    Citation,
    Classification,
    ExtractedField,
    Extraction,
    FieldValidationError,
    MissingDocument,
    MissingDocuments,
)
from iris_agents.templates import TemplateLoader

__all__ = [
    "AgentError",
    "AgentLLMError",
    "AgentValidationError",
    "Citation",
    "Classification",
    "ExtractedField",
    "Extraction",
    "FieldValidationError",
    "MissingDocument",
    "MissingDocuments",
    "TemplateLoader",
]
