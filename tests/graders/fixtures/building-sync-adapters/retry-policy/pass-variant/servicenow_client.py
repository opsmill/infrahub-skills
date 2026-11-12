from random import uniform
from time import sleep

import requests


def _is_retryable(status):
    return status in (429, 502, 503, 504)


class Policy:
    def __init__(self):
        self.retry_after_cap = 300
        self.backoff_cap = 60
        self.attempts = 4

    def delay(self, attempt):
        delay = 2 ** attempt + uniform(0, 1)
        if delay > self.backoff_cap:
            delay = self.backoff_cap
        return delay


def fetch(session, url, policy=None):
    policy = policy or Policy()
    for attempt in range(policy.attempts):
        try:
            resp = session.get(url, timeout=60)
        except requests.RequestException as exc:
            if isinstance(exc, requests.exceptions.SSLError):
                raise
            sleep(policy.delay(attempt))
            continue
        if not _is_retryable(resp.status_code):
            return resp
        header = resp.headers["retry-after"] if "retry-after" in resp.headers else None
        wait = float(header) if header else policy.delay(attempt)
        if wait > policy.retry_after_cap:
            raise RuntimeError(f"rate limited for {wait} s; giving up")
        sleep(wait)
    raise RuntimeError("retries exhausted")
