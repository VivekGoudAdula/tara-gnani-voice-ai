"""Simple in-memory sliding window rate limiter for authentication endpoints."""

import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

# In-memory request timestamp storage: ip -> list of request timestamps
_request_history: dict[str, list[float]] = defaultdict(list)

MAX_REQUESTS_PER_MINUTE = 10
WINDOW_SECONDS = 60.0


def check_rate_limit(request: Request) -> None:
    """
    Enforce rate limit of MAX_REQUESTS_PER_MINUTE requests per client IP.
    Raises HTTPException(429) if exceeded.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    # Filter timestamps older than window
    timestamps = [t for t in _request_history[client_ip] if t > cutoff]
    if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

    timestamps.append(now)
    _request_history[client_ip] = timestamps


def reset_rate_limits() -> None:
    """Reset rate limiter state (used in testing)."""
    _request_history.clear()
