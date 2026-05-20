# Plan 005: Classification and Extraction Agents

**Workstream**: `005-classification-extraction-agents`
**Status**: Draft
**Specification**: [spec.md](./spec.md)

## Approach

Two agents in `iris-agents`: `DocumentClassifier` and `FieldExtractor`. Each is a small class that takes its dependencies (LLMProvider, OCREngine, prompt template, schema) at construction time. The agents do not import adapters; they import only the Protocols.

The PoC's `document_classifier.py` and `field_extractor.py` are the reference implementations. The lift involves:

1. Replacing direct Azure OpenAI calls with the `LLMProvider` Protocol.
2. Replacing the hard-coded prompts with templates from the Product bundle.
3. Replacing the bespoke result types with typed Pydantic models that map to the contract.
4. Adding telemetry around every call.

## Proposed file layout

```
packages/iris-agents/
├── pyproject.toml
└── src/iris_agents/
    ├── __init__.py
    ├── classifier.py            # DocumentClassifier
    ├── extractor.py             # FieldExtractor
    ├── templates.py             # Jinja2 template loading from a Product bundle
    ├── results.py               # Classification, Extraction, FieldValidationError
    └── errors.py                # AgentError, AgentLLMError, AgentValidationError

packages/iris-agents/tests/
├── test_classifier_unit.py      # against StubLLMProvider; deterministic
├── test_extractor_unit.py
├── test_template_loading.py
├── golden/
│   ├── fnol-001.pdf
│   ├── fnol-001.expected.json
│   ├── police-report-001.pdf
│   ├── police-report-001.expected.json
│   └── ...
└── test_golden.py               # gated on `--golden` marker; runs the matrix
```

## Key choices

1. **Agents are plain async classes**. No framework, no LangChain. The dependency injection is constructor arguments; the runtime is `asyncio`.
2. **Prompts are Jinja2 templates** loaded from the Product bundle's `prompts/` directory. Variables are declared in the bundle's `prompts.yaml` (workstream 002).
3. **Results are Pydantic models**. The LLM adapter's structured-output mechanism populates them directly; no parsing layer in the agent.
4. **Telemetry is one OTEL span per agent call**, with the attributes listed in spec User Story 8.
5. **The golden set is a marker-gated suite** (`pytest -m golden`). Default `make test` does not run it; CI runs it separately.

## Configuration shape (consumed from workstream 002)

The relevant Product bundle slices:

```yaml
# taxonomy.yaml
document_types:
  - id: fnol_form
    description: First Notice of Loss form
    required_documents:
      - fnol_form
      - drivers_license
      - vehicle_registration
  - id: police_report
    description: Police report for an incident
  # ...

# extraction.yaml
fields:
  - id: claim_amount
    type: number
    required: true
    validators:
      - min_value: 0
  - id: incident_date
    type: date
    required: true
    validators:
      - iso_8601
  # ...

# prompts/classify.j2
You are classifying an insurance document for {{ product.line_of_business }}.
The valid document types are:
{% for dt in taxonomy.document_types %}
- {{ dt.id }}: {{ dt.description }}
{% endfor %}
...

# prompts/extract.j2
Extract the following fields from the document...
```

## Out of scope

- Summarisation. Follow-up task.
- Fraud signals. Later workstream.
- Cross-document extraction (e.g., reconciling fields across two pages of two different documents). Out of scope here; agents see one document at a time.

## Dependencies

- Workstream 001 (scaffold).
- Workstream 002 (configuration framework) for the Product bundle.
- Workstream 003 (OCR adapters) for the input.
- Workstream 004 (LLM adapters) for the structured-output Protocol.
