---
title: Apply the Default Retry and Rate-Limit Policy
impact: HIGH
description: >-
  The adapter's HTTP client retries 429, 502, 503 and 504 and dropped or
  timed-out connections from one shared budget, honors Retry-After but stops
  with an error above 300 s, otherwise backs off exponentially with jitter
  capped at 60 s, and never retries TLS errors. Values in api-behavior.yml
  override the defaults.
tags: retry, rate-limit, retry-after, backoff, tls, http-client
---

## Apply the Default Retry and Rate-Limit Policy

Give the adapter's HTTP client this policy in the first
version, complete, instead of adding one case after each
failure:

- Retry HTTP 429, 502, 503 and 504, and dropped or
  timed-out connections, from **one shared retry
  budget**.
- Honor `Retry-After` in full. When it asks for more
  than **300 s**, raise an error instead of waiting, and
  name the reset time when the API sends one.
- Without `Retry-After`, back off exponentially with
  random jitter, **capped at 60 s**.
- Never retry TLS errors: certificate failures and TLS
  protocol errors do not go away on a second attempt.

Values recorded in `api-behavior.yml` override the
defaults: `rate_limit.max_retry_after` replaces the
300 s limit (only after the user approves a longer
wait), `rate_limit.retry_statuses` replaces the status
set, and `rate_limit.reset_header` names the reset
header.

### Why it matters

- **Microsoft Graph.** The policy took three rounds of
  changes. First `Retry-After` was capped and 502 and 504
  were not retried. Then a run stopped on one page that
  took longer than the 60 s timeout, because only HTTP
  statuses were retried, not timeouts.
- **Webex.** `Retry-After` handling was added in a
  separate change.
- **Hourly rate limits.** A system with a per-hour rate
  limit answers 429 with a `Retry-After` close to the
  next full hour (up to about 3600 s). Sleeping that long
  looks like a hung run. Stopping with an error that
  names the reset time tells the operator when to run
  again.
- **TLS errors.** In `requests`,
  `requests.exceptions.SSLError` is a subclass of
  `requests.exceptions.ConnectionError`. A handler that
  retries `ConnectionError` retries certificate failures
  too, unless `SSLError` is handled first.

### Reference implementation

```python
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
```

Retry only reads (GET). Test the policy with the
captured 429 served by the fake from
[test-fakes-from-captures.md](./test-fakes-from-captures.md),
with `time.sleep` replaced, so the tests do not wait.

If you build the policy on `urllib3.util.Retry` instead,
check that it gives the same behavior, the stop above
300 s and the TLS exclusion included.

### Incorrect

A fixed sleep on 429 only, `Retry-After` ignored, no
retry on 502, 503, 504 or dropped connections, and no
limit on the number of attempts:

```python
def get(self, url, params=None):
    while True:
        response = self.session.get(url, params=params, timeout=60)
        if response.status_code == 429:
            time.sleep(5)
            continue
        response.raise_for_status()
        return response
```

### Common mistakes

- **Two budgets**, one for statuses and one for
  connection errors, so a flapping link retries twice as
  often as intended.
- **Capping `Retry-After` at the backoff cap**, which
  retries before the API allows it and spends the budget.
- **Waiting out a long `Retry-After`** instead of
  stopping with the reset time.
- **Catching `ConnectionError` before `SSLError`**, which
  retries a certificate failure.

Reference: [Retry-After, RFC 9110 section 10.2.3](https://www.rfc-editor.org/rfc/rfc9110#section-10.2.3)
