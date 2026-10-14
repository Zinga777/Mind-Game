"""CoinDCX public market data (no key). UNVERIFIED_AGAINST_LIVE_EXCHANGE."""
from __future__ import annotations

from ..base import TIMEFRAME_MS, Candle, FundingInfo, InstrumentSpec, OrderBook, Trade
from .http import Http
from .models import RESOLUTION, parse_candles, parse_funding, parse_instrument, parse_orderbook, parse_trades

MAX_CANDLES_PER_CALL = 1000


class CoinDCXPublic:
    name = "coindcx"

    def __init__(self, http: Http | None = None, api_base: str = "https://api.coindcx.com",
                 public_base: str = "https://public.coindcx.com", margin_currency: str = "INR",
                 usdt_inr_rate: float = 88.0):
        self.http = http or Http()
        self.api, self.pub = api_base.rstrip("/"), public_base.rstrip("/")
        self.margin = margin_currency
        self.q2inr = usdt_inr_rate if margin_currency == "INR" else 1.0
        self._specs: dict[str, InstrumentSpec] = {}

    # -- instruments ---------------------------------------------------------
    def active_instruments(self, margin: str | None = None) -> list[str]:
        r = self.http.request("GET", f"{self.api}/exchange/v1/derivatives/futures/data/active_instruments",
                              params={"margin_currency_short_name[]": margin or self.margin})
        return [x if isinstance(x, str) else x.get("pair") for x in r]

    def instrument_spec(self, pair: str) -> InstrumentSpec:
        if pair not in self._specs:
            r = self.http.request("GET", f"{self.api}/exchange/v1/derivatives/futures/data/instrument",
                                  params={"pair": pair, "margin_currency_short_name": self.margin})
            self._specs[pair] = parse_instrument(r, self.q2inr)
        return self._specs[pair]

    def list_instruments(self) -> list[InstrumentSpec]:
        return [self.instrument_spec(p) for p in self.active_instruments()]

    # -- market data ---------------------------------------------------------
    def candles(self, pair: str, timeframe: str, start_ms: int, end_ms: int) -> list[Candle]:
        """Paginated. CoinDCX futures candles take from/to in SECONDS and resolution '1','5','60','1D'."""
        tf = TIMEFRAME_MS[timeframe]
        res = RESOLUTION[timeframe]
        out: dict[int, Candle] = {}
        cur = start_ms
        while cur < end_ms:
            chunk_end = min(end_ms, cur + tf * MAX_CANDLES_PER_CALL)
            raw = self.http.request("GET", f"{self.pub}/market_data/candlesticks",
                                    params={"pair": pair, "from": cur // 1000, "to": chunk_end // 1000,
                                            "resolution": res, "pcode": "f"})
            for c in parse_candles(raw):
                if start_ms <= c.open_time_ms < end_ms:
                    out[c.open_time_ms] = c
            cur = chunk_end
        return [out[k] for k in sorted(out)]

    def orderbook(self, pair: str, depth: int = 50) -> OrderBook:
        r = self.http.request("GET", f"{self.pub}/market_data/v3/orderbook/{pair}-futures/{depth}")
        return parse_orderbook(r)

    def recent_trades(self, pair: str, limit: int = 100) -> list[Trade]:
        r = self.http.request("GET", f"{self.api}/exchange/v1/derivatives/futures/data/trades", params={"pair": pair})
        return parse_trades(r)[:limit]

    def funding_rate(self, pair: str) -> FundingInfo:
        spec = self.instrument_spec(pair)
        r = self.http.request("GET", f"{self.api}/exchange/v1/derivatives/futures/data/instrument",
                              params={"pair": pair, "margin_currency_short_name": self.margin})
        return parse_funding(r.get("instrument", r), spec.funding_interval_hours)

    # execution is not available on the public client
    def place_order(self, req):  # pragma: no cover - interface completeness
        raise PermissionError("public client cannot trade")

    cancel_order = positions = exit_position = place_order
