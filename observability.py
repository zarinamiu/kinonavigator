"""Необязательная отправка трасс КиноНавигатора в локальный Phoenix.

Трассировка включается только при PHOENIX_TRACING=1.
Текст запроса, user_id и session_id в атрибуты span не записываются.
"""

from __future__ import annotations

import os
import threading
from functools import wraps
from typing import Any, Callable, TypeVar


F = TypeVar("F", bound=Callable[..., Any])

_provider = None
_tracer = None
_lock = threading.Lock()


def _get_tracer():
    global _provider, _tracer

    if _tracer is not None:
        return _tracer

    with _lock:
        if _tracer is not None:
            return _tracer

        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.getenv(
            "PHOENIX_ENDPOINT",
            "http://127.0.0.1:6006/v1/traces",
        )

        provider = TracerProvider(
            resource=Resource.create({
                "service.name": "kinonavigator",
                "service.version": "0.1.0",
            })
        )
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            timeout=5,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _provider = provider
        _tracer = trace.get_tracer("kinonavigator")

    return _tracer


def trace_recommendation(func: F) -> F:

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if os.getenv("PHOENIX_TRACING") != "1":
            return func(*args, **kwargs)

        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        tracer = _get_tracer()





        algorithm = kwargs.get("algorithm", "hybrid")
        if len(args) >= 3:
            algorithm = args[2]

        with tracer.start_as_current_span("kinonavigator.recommend") as span:
            span.set_attribute("app.operation", "recommend")
            span.set_attribute("app.algorithm", str(algorithm))

            try:
                result = func(*args, **kwargs)

                if isinstance(result, dict):
                    span.set_attribute(
                        "app.result_status",
                        str(result.get("status", "unknown")),
                    )
                    recommendations = result.get("recommendations", [])
                    if isinstance(recommendations, list):
                        span.set_attribute(
                            "app.recommendation_count",
                            len(recommendations),
                        )

                return result

            except Exception as error:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute(
                    "app.error_type",
                    type(error).__name__,
                )
                raise

            finally:




                if _provider is not None:
                    _provider.force_flush(timeout_millis=5000)

    return wrapper  # type: ignore[return-value]
