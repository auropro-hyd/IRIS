"""Shared fixtures for integration tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def span_exporter() -> Generator[InMemorySpanExporter]:
    """In-memory span exporter for one test.

    Attaches to the active TracerProvider (creating one if none is set),
    so it works whether or not another conftest already set the provider.
    """
    exporter = InMemorySpanExporter()
    provider = otel_trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    exporter.clear()
