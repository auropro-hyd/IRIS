"""Shared fixtures for the OCR contract suite."""

from __future__ import annotations

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
otel_trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """Return the in-memory span exporter, cleared before and after each test."""
    _EXPORTER.clear()
    yield _EXPORTER
    _EXPORTER.clear()
