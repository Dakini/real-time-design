"""Timestamp helpers shared across the service layer and demo seed data."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
