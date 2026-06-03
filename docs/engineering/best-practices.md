# IRIS Engineering Best Practices

This document is the canonical reference for how engineering work happens on IRIS. It covers coding standards, pre-commit hygiene, testing, observability, error handling, security, documentation, AI-assisted development, and dependency management.

It applies to every line of code, every test, every workflow, and every prose document in this repository. When a rule below conflicts with anything written in `CONTRIBUTING.md`, the document with the more specific scope wins (this file for "how to write the code", `CONTRIBUTING.md` for "how to land the change").

Audience: every engineer touching IRIS, whether human or AI-assisted.

## 1. Coding standards

### 1.1 Python

| Concern | Rule |
|---|---|
| Style | `ruff` with the project's config (lifted from the existing `iris/pyproject.toml`). Line length 100. |
| Formatting | `ruff format`. No `black`, no `isort`. `ruff` covers both. |
| Type hints | Required on every public function, method, class attribute. `Any` is a code smell; prefer `object` plus a narrowing check, or a Protocol. |
| Type checking | `mypy --strict` on `iris-engine` and every adapter. Test code may relax to default. |
| Imports | Absolute imports, never relative. One import per line. Standard library, third-party, local in that order, separated by blank lines. |
| Naming | `snake_case` for functions, methods, modules. `PascalCase` for classes. `SCREAMING_SNAKE_CASE` for module-level constants. |
| Async | Default to async for anything that crosses a network or DB boundary. Sync wrappers are acceptable only in CLI entry points and tests. |
| Errors | Raise typed exceptions from `iris_engine.errors` (or the adapter's module). Never raise a bare `Exception`. Never catch a bare `Exception` except at the very top of an adapter, and then only to wrap and re-raise as a typed adapter error. |
| Logging | `structlog` with a correlation id propagated from the request. Never log secrets, PII, or full prompts. |
| Comments | Default to no comment. Write a comment only when the *why* is non-obvious (a hidden invariant, a workaround for a specific bug, a constraint imposed by an external system). Don't restate the code. |
| Docstrings | One short module-level docstring describing what the module is. Public function docstrings only when the signature isn't self-explanatory. |

### 1.2 TypeScript / JavaScript (workbench)

| Concern | Rule |
|---|---|
| Style | `eslint` plus `prettier`. The project's config lives in `apps/workbench/`. |
| Type checking | `tsc --strict`. Avoid `any`. |
| Imports | Absolute imports through the path alias defined in `tsconfig.json`. |
| Naming | `camelCase` for variables and functions. `PascalCase` for components, types, and classes. |
| State | React Query for server state, Zustand or React Context for client state. No new Redux. |
| Styles | Tailwind utility classes. CSS Modules only where Tailwind genuinely cannot express the rule. |
| Async | `async/await`, never `.then()` chains. |

### 1.3 SQL and migrations

| Concern | Rule |
|---|---|
| Migrations | `alembic`, one revision per logical change. Forward and backward migration code on every revision. |
| Tenant column | `tenant_id` is the **leading column** of every primary key, every foreign key, every index on a tenant-scoped table. |
| RLS | Every tenant-scoped table carries an RLS policy enforcing `tenant_id = current_setting('app.tenant_id')::uuid`. |
| Naming | `snake_case` for tables and columns. Plural for table names (`cases`, `claims`). Singular for join tables (`case_claimant`). |
| Foreign keys | Always named (`fk_<table>_<referenced>_<column>`). `ON DELETE` declared explicitly. |

## 2. Pre-commit, from day one

Every developer installs the project's pre-commit hooks immediately after `git clone`. The `Makefile` provides `make pre-commit-install`. The hooks are not optional; they are the project's local quality gate.

The full hook set (also documented in task T012):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-added-large-files
        args: ["--maxkb=500"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-PyYAML]
        files: '^(packages/iris-engine|packages/iris-adapters)/.*\.py$'
        args: [--strict]

  - repo: https://github.com/asottile/pyupgrade
    rev: v3.19.0
    hooks:
      - id: pyupgrade
        args: [--py312-plus]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.0
    hooks:
      - id: gitleaks
```

### Why these and not others

- `ruff` replaces `flake8`, `isort`, `pylint`, `pyupgrade` (in lint mode), and `black`. One tool, one source of style truth.
- `mypy --strict` catches a class of bugs that no test would. The cost is upfront discipline; the payoff is far fewer runtime surprises.
- Two secret scanners (`detect-secrets` and `gitleaks`) is intentional. They find different things and the cost of running both is negligible. The baseline file in `detect-secrets` is committed; new secrets fail the hook by default.
- `check-added-large-files` blocks accidental commit of binary blobs (model weights, sample PDFs).

### CI safety net

CI runs `pre-commit run --all-files` as a step. A contributor who skipped local hooks will be caught at PR time. This is the same set of gates that should have run on their machine; CI is the backstop, not the primary gate.

### Before the codebase lands

A lighter `.pre-commit-config.yaml` lives at the root today, covering only what is currently in the tree: `markdownlint`, trailing-whitespace, end-of-file-fixer, plus `scripts/check-tasks.py` as a local hook. T012 extends it with the full Python and secrets-scanning set as the codebase grows.

## 3. Testing

| Layer | Where | Purpose |
|---|---|---|
| Unit | `packages/<pkg>/tests/test_*.py` | One module, no I/O. Fast, deterministic. |
| Contract | `tests/contract/test_*.py` | Parametrised over every registered adapter for the relevant Protocol. Every adapter must pass every clause. |
| Integration | `tests/integration/test_*.py` | Two or more components together, in-memory adapters by default. |
| End-to-end | `tests/e2e/test_*.py` | Real services. Gated on `IRIS_E2E_LIVE=1` and the per-service env vars. Skipped by default. |

Rules:

1. **Coverage target: 80% lines on `iris-engine` and every adapter package.** Below this the CI gate fails. Coverage on tests themselves is not measured.
2. **Stub adapters for everything external.** `StubLLMProvider`, `InMemoryOCREngine`, `InMemoryVectorStore`, etc. live alongside the Protocol. Tests use the stub by default; live adapters only in `e2e`.
3. **No live network calls in unit or contract tests.** A test that contacts the real internet fails as a bug.
4. **One assertion per test where possible.** Multiple assertions are fine in integration tests where you're verifying a sequence of states.
5. **Test names describe the behaviour.** `test_classifier_returns_unknown_when_document_does_not_match_taxonomy`, not `test_classifier_unknown`.
6. **Property-based tests via `hypothesis` for anything with a numerical or combinatorial surface** (parsers, validators, normalisers).

## 4. Observability

Every operation that crosses a network, DB, or process boundary is wrapped in an OTEL span. Span attributes are required, not optional.

| Attribute | When | Notes |
|---|---|---|
| `tenant_id` | always | Propagated from `TenantContext`. |
| `correlation_id` | always | One per inbound request, propagated through every span. |
| `adapter_id` | adapter spans | Which adapter is active for this call. |
| `outcome` | always | `success` or a typed failure category (`auth_failed`, `rate_limited`, `unavailable`, etc.). |
| `latency_ms` | always | Server-measured, not client. |
| `input_tokens`, `output_tokens` | LLM spans | For the cost ledger. |

Logging:

- `structlog` with JSON output in production, console output in dev.
- One log line per significant transition. Don't log inside tight loops.
- **Never log**: API keys, JWT tokens, raw prompts, raw OCR output, full LLM responses, PII (names, emails, policy numbers, claim IDs).
- Errors log the exception type and message but not the stack trace by default; the stack trace goes into the OTEL exception event instead.

Metrics:

- Counter and histogram primitives from `prometheus_client` exposed at `/metrics`.
- Naming: `iris_<subsystem>_<noun>_<verb>` (`iris_ocr_pages_extracted_total`, `iris_llm_request_latency_seconds`).
- Labels are bounded. No tenant_id in a metric label (cardinality explosion).

## 5. Error handling

Every error has a type. Generic exceptions are a bug.

1. **Engine code raises types from `iris_engine.errors`.** Never raise `Exception` or `RuntimeError` in the engine.
2. **Adapter code raises adapter-specific types** that inherit from the relevant base (`OCRError`, `LLMError`, `BlobError`, etc.). Generic exceptions are caught only at the adapter's outermost layer and wrapped before re-raise.
3. **Errors carry structured context.** `class LLMUnavailable(LLMError): pass` is a start; the instance carries `model`, `adapter_id`, `cause` (the underlying exception). The API layer reads this and shapes the HTTP response.
4. **HTTP responses use the `iris.*` code namespace.** `iris.authz.denied`, `iris.ocr.unavailable`, `iris.llm.rate_limited`. The code is stable across versions; the message is not.
5. **Retries are typed.** `LLMRateLimited` triggers exponential backoff; `LLMAuthenticationFailed` does not. The retry policy is in the adapter; the engine only retries if the Product config specifies a fallback adapter.
6. **No silent failures.** A try-except that swallows a real error without re-raising or logging fails review.

## 6. Security

| Concern | Practice |
|---|---|
| Secrets in code | Never. `detect-secrets` and `gitleaks` block commits; `.env.example` documents what the code reads. |
| Secrets at rest | Vault or KMS, referenced through the outbound gateway's `secret://` notation. |
| Secrets in logs | Never. Redact at the logger level, not at the call site. |
| API keys in tests | Mock the adapter or use a fake server. Live tests load credentials from env vars at test time. |
| Outbound calls | Through the outbound gateway. Bypass requires a code review and a documented exception. |
| Egress allowlist | Every outbound host listed in the Product bundle. New hosts require a PR. |
| PII in LLM prompts | Redacted by the Model Gateway before the call. Never bypass the gateway for "just this one call". |
| Authentication | OIDC against the configured IdP. Hand-rolled JWT is a regression. |
| RLS | Verified in tests: a tenant B query against a tenant A row returns empty, not a 500. |
| Dependencies | Pinned. Dependabot opens PRs for updates. Security advisories are addressed within a week unless explicitly accepted. |

## 7. Documentation

| Artefact | Where | When |
|---|---|---|
| Spec | `specs/<NNN>-<slug>/spec.md` | Before any code on a new concern. |
| Plan | `specs/<NNN>-<slug>/plan.md` | After the spec is signed off, before tasks are written. |
| Tasks | `specs/<NNN>-<slug>/tasks.md` | After the plan. Each task has a clear acceptance criterion. |
| Architecture Decision Record | `docs/adr/<NNNN>-<slug>.md` | When a load-bearing decision is made or reversed. |
| Module docstring | top of every `__init__.py` | One paragraph: what this module is for, the key types it exposes. |
| API endpoint docs | OpenAPI from FastAPI | Automatic; review the rendered output before merging endpoint changes. |
| Adapter README | `packages/iris-adapters/<name>/README.md` | What the adapter is, what env vars it reads, what its limitations are. |

A change that ships without the matching spec / plan / ADR update is incomplete. Reviewers reject these PRs.

## 8. AI-assisted development

AI assistants are encouraged. The rules below keep them from becoming a liability.

1. **You commit, you review.** Every line of AI-generated code must be read by the engineer who is committing it. "I trusted the model" is not an acceptable explanation in code review.
2. **House style wins.** If the AI generates code that does not match the conventions in this document, you rewrite it to match before commit. Do not adapt the conventions to the AI.
3. **No copy-paste from chat into the repo.** Use a tool that preserves the structure (Cursor, Copilot in IDE, etc.). Pasting from a chat window strips diff context and encourages skipping the review step.
4. **Don't commit code you don't understand.** If you cannot explain why a line is there, either understand it or delete it.
5. **Be deliberate about context.** Give the AI the spec, the relevant Protocol, and the test surface. Don't give it a `__init__.py` and hope.
6. **AI does not approve PRs.** A code-review approval is a human signoff. A bot comment is informational, not authoritative.
7. **Prompts are not commits.** Do not commit prompt strings as if they were code; treat them as a configuration concern (in the Product bundle's `prompts/` directory, version-controlled, code-reviewed).

## 9. Dependency management

| Stack | Tool | Lockfile |
|---|---|---|
| Python | `uv` | `uv.lock` |
| JavaScript | `pnpm` | `pnpm-lock.yaml` |
| System | `docker` (`docker compose` for dev) | image digests in compose |

Rules:

1. **Lockfiles are committed.** Always.
2. **New direct dependencies require a paragraph in the PR description.** What you tried first, why the new dep is the right answer, what the maintenance posture of the package is (last release, GitHub stars, alternatives).
3. **Transitive dependencies are not a concern as long as the lockfile resolves and the security scanners are clean.**
4. **Dependabot grouped weekly updates** for minor and patch. Majors come as individual PRs and require an additional reviewer.
5. **Pinned versions in workflow files** (e.g., `markdownlint-cli@0.41.0`, not `markdownlint-cli@latest`). Dependabot opens a PR when a new version is available.
6. **Removing a dependency is easier than adding one**: if a package is used in fewer than three places, prefer inlining the small piece you actually need.

## 10. What we explicitly do not do

A short list to keep the conventions sharp.

- **No `Any` to silence mypy.** Either type it properly or use a Protocol.
- **No `# type: ignore` without a reason comment.** Reviewers reject these.
- **No "TODO" comments without a tracking issue.** "TODO: handle the edge case" goes in the project tracker, not the source.
- **No commented-out code.** If it is not in use, delete it. Git remembers.
- **No magic numbers in code.** Name them or pull them from configuration.
- **No silent fallbacks.** If a primary fails and the fallback succeeds, the event log records it. Failures must be visible.
- **No bypassing pre-commit hooks.** `git commit --no-verify` is a smell; use it only when you are certain the hook is wrong and you are opening a follow-up PR to fix the hook.
- **No personal names in code or commit messages.** Refer to people by GitHub handle when necessary.
- **No em-dashes in prose.** Project style. Use a period, a comma, a colon, or parentheses.

## 11. Reviewing changes against this document

This document is enforced by:

1. The CI workflows (lint, type-check, test, coverage, security scan).
2. The pre-commit hook set.
3. The PR review process. Reviewers explicitly check against these conventions.
4. Periodic engineering retros (quarterly), where the document is updated based on what is working and what is friction.

Proposed changes to this document go through a PR like any other change. Treat it as a contract.

## 12. Tooling cheat sheet

```bash
# After git clone
make install
make pre-commit-install

# Day-to-day
make lint            # ruff check
make fmt             # ruff format
make typecheck       # mypy --strict
make test            # pytest, default markers
make test-cov        # with coverage report
make contract        # contract tests only
make e2e             # end-to-end (requires IRIS_E2E_LIVE=1 and the stack up)

# Before opening a PR
pre-commit run --all-files
make lint && make typecheck && make test-cov

# When something is wrong with the hook itself
pre-commit autoupdate     # bump hook versions
pre-commit clean          # clear cached envs
```
