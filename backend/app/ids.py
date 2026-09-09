"""ID and token generation."""

import itertools
import secrets
import time

_counter = itertools.count(1)


def new_id(prefix: str) -> str:
    n = next(_counter)
    rand = secrets.token_hex(3)
    return f"{prefix}_{int(time.time() * 1000):x}{n:x}{rand}"


def secure_token() -> str:
    """128+ bits of entropy, hex encoded — used for guest link tokens."""
    return secrets.token_hex(16)
