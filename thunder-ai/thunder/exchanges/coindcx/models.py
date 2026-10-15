"""Parse CoinDCX JSON into exchange-neutral models.

Field names follow the third-party `coindcx` client docstrings and spec 6.2.
UNVERIFIED_AGAINST_LIVE_EXCHANGE: parsing is tolerant (several candidate keys)
and each parser is tested against fixtures in tests/fixtures/ that mirror the
documented shapes, not captured live responses.
"""
from __future__ import annotations

from ..base import Candle, FundingInfo, InstrumentSpec, OrderBook, Trade


def _f(d: dict, *keys: str, default: float | None = None) -> float | None:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return default


def parse_instrument(raw: dict, quote_to_inr: float = 1.0) -> InstrumentSpec:
    d = raw.get("instrument", raw)
    # Fees are documented as PERCENT values (0.02 means 0.02%), so divide by 100.
    maker = _f(d, "maker_fee", default=0.02) / 100.0
    taker = _f(d, "taker_fee", default=0.05) / 100.0
    return InstrumentSpec(
        pair=d.get("pair") or d.get("symbol") or "",
        margin_currency=d.get("margin_currency_short_name", "USDT"),
        min_qty=_f(d, "min_quantity", "min_trade_size", default=0.001),
        qty_step=_f(d, "quantity_increment", default=0.001),
        tick=_f(d, "price_increment", default=0.1),
        contract_value=_f(d, "contract_value", "multiplier", default=1.0),
        max_leverage=min(_f(d, "max_leverage_long", "max_leverage", default=20.0),
                         _f(d, "max_leverage_short", "max_leverage", default=20.0)),
        maker_fee=maker,
        taker_fee=taker,
        funding_interval_hours=_f(d, "funding_frequency", default=8.0),
        min_notional=_f(d, "min_notional", default=0.0),
        quote_to_inr=quote_to_inr,
        maintenance_margin_rate=_f(d, "maintenance_margin_rate", "maintenance_margin", default=0.005),
        status=d.get("status", "active"),
        verified=True,
    )


def parse_candles(raw) -> list[Candle]:
    rows = raw.get("data", []) if isinstance(raw, dict) else raw
    out = []
    for r in rows:
        t = int(r.get("time") or r.get("open_time") or r.get("t"))
        if t < 10_000_000_000:  # seconds -> ms
            t *= 1000
        out.append(Candle(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                          float(r.get("volume", 0.0))))
    out.sort(key=lambda c: c.open_time_ms)
    return out


def parse_orderbook(raw: dict) -> OrderBook:
    def side(x):
        if isinstance(x, dict):
            items = [(float(p), float(q)) for p, q in x.items()]
        else:
            items = [(float(p), float(q)) for p, q in x]
        return items
    bids = sorted(side(raw.get("bids", {})), key=lambda t: -t[0])
    asks = sorted(side(raw.get("asks", {})), key=lambda t: t[0])
    return OrderBook(bids=bids, asks=asks, ts_ms=int(raw.get("ts", 0) or 0))


def parse_trades(raw) -> list[Trade]:
    out = []
    for r in raw:
        out.append(Trade(price=float(r.get("price", r.get("p"))), qty=float(r.get("quantity", r.get("q", 0))),
                         ts_ms=int(r.get("timestamp", r.get("T", 0))), is_buyer_maker=r.get("is_maker", r.get("m"))))
    return out


def parse_funding(raw: dict, interval_hours: float = 8.0) -> FundingInfo:
    rate = _f(raw, "funding_rate", "fr", "current_funding_rate", default=0.0)
    nxt = raw.get("next_funding_time")
    return FundingInfo(rate=rate or 0.0, next_funding_ms=int(nxt) if nxt else None, interval_hours=interval_hours)


RESOLUTION = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "1D"}
