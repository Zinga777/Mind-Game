"""CoinDCX request signing.

Documented scheme (spec 6.2; matches the third-party `coindcx` PyPI client):
  body includes "timestamp" (ms);
  signature = HMAC-SHA256(json.dumps(body, separators=(',', ':')), secret).hexdigest()
  headers: X-AUTH-APIKEY, X-AUTH-SIGNATURE, Content-Type: application/json
UNVERIFIED_AGAINST_LIVE_EXCHANGE (docs.coindcx.com was unreachable at build time).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time


def compact_json(body: dict) -> str:
    return json.dumps(body, separators=(",", ":"))


def sign(body: dict, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), compact_json(body).encode("utf-8"), hashlib.sha256).hexdigest()


def signed_request(body: dict, api_key: str, secret: str, timestamp_ms: int | None = None) -> tuple[str, dict]:
    body = dict(body)
    body.setdefault("timestamp", timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    payload = compact_json(body)
    headers = {"Content-Type": "application/json", "X-AUTH-APIKEY": api_key,
               "X-AUTH-SIGNATURE": sign(body, secret)}
    return payload, headers
