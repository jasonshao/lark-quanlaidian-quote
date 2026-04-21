"""Simple retry decorator with fixed backoff sequence.

Usage:
    @retry(attempts=3, backoff=(1, 4, 15))
    def step(...): ...
"""

from __future__ import annotations

import functools
import time
from typing import Callable, Sequence


class RetryExhausted(Exception):
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"retry exhausted after {attempts} attempts: {last_error}")


def retry(*, attempts: int, backoff: Sequence[float]):
    """Decorator: retry `fn` up to `attempts` times with gaps from `backoff`.

    `backoff` is the delay *between* attempts. For attempts=3, backoff=(1,4,15),
    the flow is: try → sleep 1 → try → sleep 4 → try → fail.
    The final element of backoff is ignored (there's no post-final-attempt sleep).
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if len(backoff) < attempts - 1:
        raise ValueError(f"backoff must have at least {attempts - 1} entries")

    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error: Exception | None = None
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if i < attempts - 1:
                        time.sleep(backoff[i])
            raise RetryExhausted(attempts=attempts, last_error=last_error)
        return wrapper
    return decorator
