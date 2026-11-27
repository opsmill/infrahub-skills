"""HTTP client for the ServiceNow Table API: the default policy, but TLS errors are retried before they are raised."""

import random
import time

import requests

RETRY_STATUSES = frozenset({429, 502, 503, 504})
MAX_RETRY_AFTER = 300
BACKOFF_CAP = 60


class RateLimitWaitTooLong(RuntimeError):
    """ServiceNow asked for a wait longer than the policy allows."""


class ServiceNowClient:
    def __init__(self, session, max_retries=5):
        self.session = session
        self.max_retries = max_retries

    def get(self, url, params=None):
        attempt = 0
        while True:
            try:
                resp = self.session.get(url, params=params, timeout=60)
            except (requests.ConnectionError, requests.Timeout) as exc:
                # SSLError subclasses ConnectionError: give up on it, but only after a few tries
                if isinstance(exc, requests.exceptions.SSLError) and attempt >= 2:
                    raise
                attempt += 1
                if attempt > self.max_retries:
                    raise
                time.sleep(self._backoff(attempt))
                continue
            if resp.status_code not in RETRY_STATUSES:
                return resp
            attempt += 1
            if attempt > self.max_retries:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                wait = float(retry_after)
                if wait > MAX_RETRY_AFTER:
                    reset = resp.headers.get("X-RateLimit-Reset")
                    raise RateLimitWaitTooLong(f"ServiceNow rate limit: retry after {wait:.0f} s (window resets at {reset})")
            else:
                wait = self._backoff(attempt)
            time.sleep(wait)

    def _backoff(self, attempt):
        return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)
