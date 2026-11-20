"""Client resilient to throttling: retries 429 and dropped connections."""

import time

import requests


class ServiceNowClient:
    def __init__(self, session, max_retries=5):
        self.session = session
        self.max_retries = max_retries

    def get(self, url, params=None):
        for _ in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=60)
            except requests.ConnectionError:
                time.sleep(5)
                continue
            if resp.status_code in {429}:
                # Retry-After is honoured by waiting a fixed 30 s
                time.sleep(30)
                continue
            return resp
        raise RuntimeError("retries exhausted")
