"""Core health-check logic.

Performs a single HTTP request against a URL and records the outcome as a Check
row. A monitor is considered "up" only for 2xx/3xx responses. Any 4xx/5xx
response, or any network-level failure (DNS error, connection refused, timeout),
counts as "down".
"""
import time

import httpx

from .models import Check

REQUEST_TIMEOUT_SECONDS = 10


def check_url(url: str) -> Check:
    """Ping a single URL and return an unsaved Check describing the result."""
    started = time.perf_counter()
    try:
        # follow_redirects so a 301/302 to a healthy page still counts as up.
        response = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": "uptime-monitor/1.0"},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Check(
            status_code=response.status_code,
            response_time_ms=round(elapsed_ms, 1),
            is_up=200 <= response.status_code < 400,
            error=None,
        )
    except httpx.HTTPError as exc:
        # DNS failure, connection refused, timeout, invalid host, etc.
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Check(
            status_code=None,
            response_time_ms=round(elapsed_ms, 1),
            is_up=False,
            error=f"{type(exc).__name__}: {exc}",
        )
