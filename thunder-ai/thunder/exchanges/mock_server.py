"""In-process mock of the CoinDCX REST API, used by tests and the demo.

It plugs into `Http(session=MockCoinDCX(...))`, verifies HMAC signatures exactly
like the documented scheme, records every call (so tests can assert the bot
never touched a withdrawal/transfer endpoint) and simulates orders/positions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from urllib.parse import urlparse

import numpy as np


@dataclass
class _Resp:
    status_code: int
    payload: object
    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300
    @property
    def text(self) -> str:
        return json.dumps(self.payload)
    def json(self):
        return self.payload


@dataclass
class MockCoinDCX:
    api_key: str = "mock-key-123456"
    api_secret: str = "mock-secret-abcdef"
    price: float = 100.0
    calls: list[tuple[str, str]] = field(default_factory=list)
    orders: dict[str, dict] = field(default_factory=dict)
    positions: dict[str, dict] = field(default_factory=dict)
    fail_tpsl: bool = False
    fail_status: dict[str, int] = field(default_factory=dict)  # path -> forced status
    candles_5m_missing: bool = False
    _oid: int = 0

    # requests.Session-compatible ------------------------------------------------
    def request(self, method, url, params=None, data=None, headers=None, timeout=None):
        path = urlparse(url).path
        self.calls.append((method, path))
        if path in self.fail_status:
            return _Resp(self.fail_status[path], {"message": "forced failure"})
        if method == "POST":
            body = json.loads(data or "{}")
            sig = hmac.new(self.api_secret.encode(), json.dumps(body, separators=(",", ":")).encode(),
                           hashlib.sha256).hexdigest()
            if (headers or {}).get("X-AUTH-APIKEY") != self.api_key or headers.get("X-AUTH-SIGNATURE") != sig:
                return _Resp(401, {"message": "Invalid signature"})
            return self._private(path, body)
        return self._public(path, params or {})

    # public ---------------------------------------------------------------------
    def _public(self, path, params):
        if path.endswith("/active_instruments"):
            return _Resp(200, ["B-BTC_USDT", "B-ETH_USDT"])
        if path.endswith("/data/instrument"):
            return _Resp(200, {"instrument": {
                "pair": params.get("pair"), "margin_currency_short_name": params.get("margin_currency_short_name"),
                "min_quantity": "0.001", "quantity_increment": "0.001", "price_increment": "0.1",
                "max_leverage_long": "50", "max_leverage_short": "50", "maker_fee": "0.02", "taker_fee": "0.05",
                "funding_frequency": "8", "min_notional": "5", "status": "active", "funding_rate": "0.0001"}})
        if path.endswith("/candlesticks"):
            res = params["resolution"]
            if res == "5" and self.candles_5m_missing:
                return _Resp(200, {"s": "ok", "data": []})
            step = {"1": 60, "5": 300, "15": 900, "60": 3600, "1D": 86400}[res]
            f, t = int(params["from"]), int(params["to"])
            start = ((f + step - 1) // step) * step
            ts = np.arange(start, t, step)[:1000]
            rng = np.random.default_rng(int(start) % 10_000)
            data = []
            p = self.price
            for x in ts:
                o = p; c = p * (1 + rng.normal(0, 0.001)); h = max(o, c) * 1.0005; lo = min(o, c) * 0.9995
                data.append({"open": o, "high": h, "low": lo, "close": c, "volume": 10.0, "time": int(x) * 1000})
                p = c
            return _Resp(200, {"s": "ok", "data": data})
        if "/orderbook/" in path:
            p = self.price
            return _Resp(200, {"ts": 0, "bids": {str(p - 0.1 * i): "5" for i in range(1, 30)},
                               "asks": {str(p + 0.1 * i): "5" for i in range(1, 30)}})
        if path.endswith("/data/trades"):
            return _Resp(200, [{"price": self.price, "quantity": 1, "timestamp": 0, "is_maker": True}])
        if path.endswith("/time"):
            return _Resp(200, {"server_time": 0})
        return _Resp(404, {"message": "not found"})

    # private --------------------------------------------------------------------
    def _private(self, path, body):
        if any(w in path for w in ("withdraw", "transfer")):
            return _Resp(403, {"message": "forbidden in mock"})
        if path.endswith("/futures/wallets"):
            return _Resp(200, [{"currency_short_name": "INR", "balance": "3000", "locked_balance": "0"}])
        if path.endswith("/orders/create"):
            o = body["order"]
            self._oid += 1
            oid = f"o{self._oid}"
            rec = {"id": oid, "status": "open", **o}
            if o["order_type"] == "market_order":
                rec["status"] = "filled"
                pid = f"p-{o['pair']}"
                sgn = 1 if o["side"] == "buy" else -1
                pos = self.positions.setdefault(pid, {"id": pid, "pair": o["pair"], "active_pos": 0.0,
                                                      "avg_price": self.price})
                pos["active_pos"] += sgn * float(o["total_quantity"])
                if abs(pos["active_pos"]) < 1e-12:
                    self.positions.pop(pid)
            self.orders[oid] = rec
            return _Resp(200, [rec])
        if path.endswith("/orders/cancel"):
            o = self.orders.get(body["id"])
            if not o:
                return _Resp(404, {"message": "no order"})
            o["status"] = "cancelled"
            return _Resp(200, {"message": "cancelled"})
        if path.endswith("/futures/orders"):
            return _Resp(200, list(self.orders.values()))
        if path.endswith("/futures/positions"):
            return _Resp(200, list(self.positions.values()))
        if path.endswith("/positions/exit"):
            self.positions.pop(body["id"], None)
            return _Resp(200, {"message": "exited"})
        if path.endswith("/create_tpsl"):
            if self.fail_tpsl:
                return _Resp(422, {"message": "tpsl rejected"})
            return _Resp(200, {"stop_loss": {"id": "sl1"}, "take_profit": {"id": "tp1"}})
        if path.endswith("/update_leverage"):
            return _Resp(200, {"message": "ok"})
        return _Resp(404, {"message": "not found"})

    def touched_forbidden(self) -> bool:
        return any(w in p for _, p in self.calls for w in ("withdraw", "transfer"))
