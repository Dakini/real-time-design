# Observability stack

A separate Compose project (`docker compose up -d` from this directory) from
the application stack in the repo root: OpenTelemetry Collector, Prometheus,
Loki, Tempo, and Grafana (`http://localhost:3000`, anonymous Viewer access).

The collector is the only thing the app talks to - it fans traces out to
Tempo, logs out to Loki, and exposes metrics for Prometheus to scrape (see
`otel-collector-config.yaml`). Point the backend at it by setting
`OTEL_EXPORTER_OTLP_ENDPOINT`:

- **Running the backend directly on the host** (`make backend` /
  `make dev`): `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` - the
  collector's OTLP port is published to the host, so this just works.
- **Running the containerized app stack** (`make up`): plain `make up` does
  *not* connect to this stack at all - the app has nowhere to send telemetry,
  so it just prints spans/metrics/logs to `docker compose logs app` (see
  `backend/app/telemetry.py`). Use `make up-observed` instead (after
  `make observability-up`): it attaches the app container to this project's
  network and sets `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
  for it (see `infra/docker-compose.otel.yaml`).

Without `OTEL_EXPORTER_OTLP_ENDPOINT` set, this stack is entirely optional -
the app runs fine without it.
