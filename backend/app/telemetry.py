"""OpenTelemetry setup: traces, metrics, and logs.

All three signals share one Resource, so every span, metric, and log line is
identifiable as coming from this service, this environment (dev/production),
and this exact deployed version - the image tag set by the deploy (see
infra/ec2-stack.yaml), not just the repo's static app version.

Everything exports via OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set
(e.g. to a collector); otherwise it prints to the console so local dev still
shows telemetry without needing a collector running.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy import Engine


def _resource() -> Resource:
    return Resource.create(
        {
            SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "linewarmer-backend"),
            DEPLOYMENT_ENVIRONMENT: os.environ.get("ENVIRONMENT", "development"),
            SERVICE_VERSION: os.environ.get("APP_VERSION", "dev"),
        }
    )


def setup_telemetry(app: FastAPI, engine: Engine) -> None:
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    resource = _resource()

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter() if otlp_endpoint else ConsoleSpanExporter()
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_exporter = OTLPMetricExporter() if otlp_endpoint else ConsoleMetricExporter()
    meter_provider = MeterProvider(
        resource=resource, metric_readers=[PeriodicExportingMetricReader(metric_exporter)]
    )
    metrics.set_meter_provider(meter_provider)

    # Logs: attaches a handler to the root logger, so every `logging` call
    # anywhere in the app (and in libraries using stdlib logging) is exported
    # too, each tagged with the trace/span id of the request it happened in.
    logger_provider = LoggerProvider(resource=resource)
    log_exporter = OTLPLogExporter() if otlp_endpoint else ConsoleLogRecordExporter()
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)
    LoggingInstrumentor().instrument(set_logging_format=True)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, meter_provider=meter_provider)
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=tracer_provider)
