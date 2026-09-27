"""Custom application metrics.

Instruments are created from a meter bound to the global MeterProvider set up
in telemetry.py, so every data point already carries that Resource - service
name, deployment environment, and deployed version - without needing to be
repeated as attributes here. The collector promotes those resource attributes
onto Prometheus labels (see observability/otel-collector-config.yaml).
"""

from __future__ import annotations

from opentelemetry import metrics

_meter = metrics.get_meter("linewarmer.backend")

rooms_created = _meter.create_counter(
    "interview.rooms.created",
    unit="{room}",
    description="Interview rooms (sessions) created",
)

participants_active = _meter.create_up_down_counter(
    "interview.participants.active",
    unit="{participant}",
    description="Currently active interview participants (joined, not yet removed)",
)

canvas_elements_created = _meter.create_counter(
    "canvas.elements.created",
    unit="{element}",
    description="Canvas elements created",
)

canvas_component_creation_failures = _meter.create_counter(
    "canvas.component_creation.failures",
    unit="{failure}",
    description="Failures while creating a canvas component",
)
