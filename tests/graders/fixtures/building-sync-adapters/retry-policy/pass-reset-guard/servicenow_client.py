"""The retry client from retry-default-policy.md, copied as a model following the rule would."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

# Defaults. Replace a value when api-behavior.yml records a different one.
RETRY_STATUSES = frozenset({429, 502, 503, 504})
MAX_RETRIES = 5  # one budget for status and connection retries
MAX_RETRY_AFTER = 300  # seconds; a longer Retry-After stops the run
BACKOFF_BASE = 2.0
BACKOFF_CAP = 60.0
RESET_HEADER = "X-RateLimit-Reset"  # rate_limit.reset_header, or None when the API sends none


class RateLimitWaitTooLongError(RuntimeError):
    """The API asked the client to wait longer than a run accepts."""


def _retry_after_seconds(value: str | None) -> float | None:
    """Retry-After as seconds; the header is either a number or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _backoff(attempt: int) -> float:
    """Exponential backoff with full jitter, capped."""
    return random.uniform(1.0, max(1.0, min(BACKOFF_CAP, BACKOFF_BASE * 2**attempt)))


class NetinventoryClient:
    def __init__(self, session: requests.Session, timeout: float = 30) -> None:
        self.session = session
        self.timeout = timeout

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        attempt = 0
        while True:
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.exceptions.SSLError:
                raise  # certificate or TLS protocol error: a retry cannot fix it
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                if attempt >= MAX_RETRIES:
                    raise
                wait = _backoff(attempt)
                logger.warning("%s: %s, retry %d/%d in %.1f s", url, type(exc).__name__, attempt + 1, MAX_RETRIES, wait)
            else:
                if response.status_code not in RETRY_STATUSES or attempt >= MAX_RETRIES:
                    response.raise_for_status()
                    return response
                retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                if retry_after is not None and retry_after > MAX_RETRY_AFTER:
                    reset = response.headers.get(RESET_HEADER) if RESET_HEADER else None
                    try:
                        resets_at = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat() if reset else None
                    except (ValueError, OverflowError, OSError):
                        resets_at = None  # milliseconds, a date string or out of range: report without it
                    msg = (
                        f"{url}: HTTP {response.status_code}, the API asks to wait {retry_after:.0f} s, "
                        f"more than the {MAX_RETRY_AFTER} s limit"
                        + (f"; the rate limit resets at {resets_at}" if resets_at else "")
                    )
                    raise RateLimitWaitTooLongError(msg)
                wait = retry_after if retry_after is not None else _backoff(attempt)
                logger.warning("%s: HTTP %d, retry %d/%d in %.1f s", url, response.status_code, attempt + 1, MAX_RETRIES, wait)
            attempt += 1
            time.sleep(wait)
