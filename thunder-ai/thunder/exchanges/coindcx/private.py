"""CoinDCX authenticated futures endpoints. UNVERIFIED_AGAINST_LIVE_EXCHANGE.

This class only knows how to talk to the exchange. It is never constructed
directly by trading code: thunder.execution.live.LiveAdapter wraps it and
refuses every call unless all Section 17 gates pass.

The bot NEVER moves money: there is deliberately no wallet-transfer,
withdrawal or sub-account-transfer method here (tested).
"""
from __future__ import annotations

import time

from ..base import OrderAck, OrderRequest, Position
from .auth import signed_request
from .http import Http

ORDER_TYPE = {"market": "market_order", "limit": "limit_order", "stop_market": "stop_market",
              "stop_limit": "stop_limit", "take_profit_market": "take_profit_market",
              "take_profit_limit": "take_profit_limit"}

FORBIDDEN_PATH_WORDS = ("withdraw", "transfer", "wallet/transfer", "sub_account")


class CoinDCXPrivate:
    def __init__(self, api_key: str, api_secret: str, http: Http | None = None,
                 api_base: str = "https://api.coindcx.com", margin_currency: str = "INR"):
        self._key, self._secret = api_key, api_secret
        self.http = http or Http(rate_per_s=5)
        self.api = api_base.rstrip("/")
        self.margin = margin_currency

    def _post(self, path: str, body: dict) -> object:
        if any(w in path for w in FORBIDDEN_PATH_WORDS):
            raise PermissionError("THUNDER never moves funds")
        payload, headers = signed_request(body, self._key, self._secret)
        return self.http.request("POST", f"{self.api}{path}", data=payload, headers=headers)

    def server_time_ms(self) -> int | None:
        """Exchange clock in ms, or None if it cannot be read (callers must then refuse to trade)."""
        try:
            r = self.http.request("GET", f"{self.api}/exchange/v1/time")
            return int(r.get("server_time", r.get("serverTime")))
        except Exception:
            return None

    def balances(self) -> object:
        return self._post("/exchange/v1/derivatives/futures/wallets", {})

    def positions(self) -> list[Position]:
        raw = self._post("/exchange/v1/derivatives/futures/positions",
                         {"page": "1", "size": "50", "margin_currency_short_name": [self.margin]})
        out = []
        for p in raw or []:
            qty = float(p.get("active_pos", 0) or 0)
            if qty == 0:
                continue
            out.append(Position(position_id=str(p.get("id")), pair=p.get("pair"), side="long" if qty > 0 else "short",
                                qty=abs(qty), entry_price=float(p.get("avg_price", 0) or 0)))
        return out

    def place_order(self, req: OrderRequest) -> OrderAck:
        order = {"side": req.side, "pair": req.pair, "order_type": ORDER_TYPE[req.order_type],
                 "total_quantity": req.qty, "client_order_id": req.client_order_id,
                 "margin_currency_short_name": self.margin, "notification": "no_notification"}
        if req.price is not None:
            order["price"] = req.price
        if req.stop_price is not None:
            order["stop_price"] = req.stop_price
        if req.leverage is not None:
            order["leverage"] = req.leverage
        if req.order_type in ("limit", "stop_limit", "take_profit_limit"):
            order["time_in_force"] = "good_till_cancel"
        if req.post_only:
            order["post_only"] = True
        raw = self._post("/exchange/v1/derivatives/futures/orders/create", {"order": order})
        o = raw[0] if isinstance(raw, list) and raw else raw
        return OrderAck(order_id=str(o.get("id")), client_order_id=req.client_order_id,
                        status=o.get("status", "unknown"), raw=o)

    def order_status(self, order_id: str) -> dict:
        raw = self._post("/exchange/v1/derivatives/futures/orders",
                         {"status": "open,filled,cancelled,partially_filled,untriggered", "page": "1", "size": "50",
                          "margin_currency_short_name": [self.margin]})
        for o in raw or []:
            if str(o.get("id")) == str(order_id):
                return o
        return {}

    def cancel_order(self, order_id: str) -> None:
        self._post("/exchange/v1/derivatives/futures/orders/cancel", {"id": order_id})

    def exit_position(self, position_id: str) -> None:
        self._post("/exchange/v1/derivatives/futures/positions/exit", {"id": position_id})

    def create_tpsl(self, position_id: str, stop_price: float, target_price: float) -> object:
        return self._post("/exchange/v1/derivatives/futures/positions/create_tpsl", {
            "id": position_id,
            "stop_loss": {"stop_price": stop_price, "order_type": "stop_market"},
            "take_profit": {"stop_price": target_price, "order_type": "take_profit_market"},
        })

    def update_leverage(self, pair: str, leverage: float) -> object:
        return self._post("/exchange/v1/derivatives/futures/positions/update_leverage",
                          {"pair": pair, "leverage": str(leverage)})
