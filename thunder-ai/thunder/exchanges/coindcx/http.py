"""Polite HTTP: token-bucket rate limit, exponential backoff on 429/5xx, scrubbed logging."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

import requests

from ...secrets import scrub

log = logging.getLogger("thunder.http")


class TokenBucket:
    def __init__(self, rate_per_s: float, burst: int = 5, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.rate, self.capacity = rate_per_s, burst
        self.tokens = float(burst)
        self.clock, self.sleep = clock, sleep
        self.t = clock()
        self.lock = threading.Lock()

    def take(self) -> None:
        with self.lock:
            while True:
                now = self.clock()
                self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                self.sleep((1 - self.tokens) / self.rate)


class HttpError(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(f"HTTP {status}: {scrub(text)[:300]}")
        self.status = status


class Http:
    def __init__(self, rate_per_s: float = 5.0, session: Optional[requests.Session] = None,
                 max_retries: int = 5, timeout: float = 15.0, sleep: Callable[[float], None] = time.sleep):
        self.bucket = TokenBucket(rate_per_s, sleep=sleep)
        self.s = session or requests.Session()
        self.max_retries, self.timeout, self.sleep = max_retries, timeout, sleep
        self.stats = {"requests": 0, "errors": 0, "last_latency_ms": 0.0}

    def request(self, method: str, url: str, *, params: dict | None = None, data: str | None = None,
                headers: dict | None = None) -> Any:
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            self.bucket.take()
            t0 = time.monotonic()
            try:
                r = self.s.request(method, url, params=params, data=data, headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                self.stats["errors"] += 1
                log.warning("network error %s %s: %s", method, url, scrub(str(e)))
                if attempt == self.max_retries:
                    raise
                self.sleep(delay); delay = min(delay * 2, 30)
                continue
            self.stats["requests"] += 1
            self.stats["last_latency_ms"] = (time.monotonic() - t0) * 1000
            log.info("%s %s -> %s (%.0f ms)", method, url, r.status_code, self.stats["last_latency_ms"])
            if r.status_code == 429 or r.status_code >= 500:
                self.stats["errors"] += 1
                if attempt == self.max_retries:
                    raise HttpError(r.status_code, r.text)
                self.sleep(delay); delay = min(delay * 2, 30)
                continue
            if not r.ok:
                self.stats["errors"] += 1
                raise HttpError(r.status_code, r.text)
            try:
                return r.json()
            except ValueError:
                return r.text
        raise RuntimeError("unreachable")
