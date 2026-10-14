"""Exchange-neutral data models and the ExchangeAdapter protocol (spec 6.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass(frozen=True)
class InstrumentSpec:
    pair: str
    margin_currency: str = "INR"
    min_qty: float = 0.001
    qty_step: float = 0.001
    tick: float = 0.1
    contract_value: float = 1.0          # units of base asset per 1 qty
    max_leverage: float = 20.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    funding_interval_hours: float = 8.0
    min_notional: float = 0.0            # in quote currency
    quote_to_inr: float = 1.0            # INR per 1 unit of quote currency
    maintenance_margin_rate: float = 0.005
    status: str = "active"
    verified: bool = False               # False => UNVERIFIED_AGAINST_LIVE_EXCHANGE


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class OrderBook:
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    ts_ms: int = 0

    @property
    def mid(self) -> float:
        return (self.bids[0][0] + self.asks[0][0]) / 2

    @property
    def spread_bps(self) -> float:
        return (self.asks[0][0] - self.bids[0][0]) / self.mid * 1e4


@dataclass(frozen=True)
class Trade:
    price: float
    qty: float
    ts_ms: int
    is_buyer_maker: Optional[bool] = None


@dataclass(frozen=True)
class FundingInfo:
    rate: float
    next_funding_ms: Optional[int] = None
    interval_hours: float = 8.0


@dataclass
class OrderRequest:
    client_order_id: str
    pair: str
    side: str                 # "buy" | "sell"
    order_type: str           # "market" | "limit" | "stop_market" | "take_profit_market"
    qty: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    leverage: Optional[float] = None
    reduce_only: bool = False
    post_only: bool = False


@dataclass
class OrderAck:
    order_id: str
    client_order_id: str
    status: str
    filled_qty: float = 0.0
    avg_price: Optional[float] = None
    raw: dict = field(default_factory=dict)


@dataclass
class Position:
    position_id: str
    pair: str
    side: str
    qty: float
    entry_price: float
    unrealised_pnl: float = 0.0


class ExchangeAdapter(Protocol):
    name: str

    def list_instruments(self) -> list[InstrumentSpec]: ...
    def instrument_spec(self, pair: str) -> InstrumentSpec: ...
    def candles(self, pair: str, timeframe: str, start_ms: int, end_ms: int) -> list[Candle]: ...
    def orderbook(self, pair: str, depth: int = 50) -> OrderBook: ...
    def recent_trades(self, pair: str, limit: int = 100) -> list[Trade]: ...
    def funding_rate(self, pair: str) -> FundingInfo: ...
    def place_order(self, req: OrderRequest) -> OrderAck: ...
    def cancel_order(self, order_id: str) -> None: ...
    def positions(self) -> list[Position]: ...
    def exit_position(self, position_id: str) -> None: ...


TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
                "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def default_spec(pair: str, quote_to_inr: float = 1.0) -> InstrumentSpec:
    """Conservative placeholder specs used until Phase 0 can read the real endpoint.

    UNVERIFIED_AGAINST_LIVE_EXCHANGE: values are typical for USDT perpetuals and
    must be replaced by the instrument endpoint's numbers on a networked machine.
    """
    if "BTC" in pair:
        return InstrumentSpec(pair, min_qty=0.001, qty_step=0.001, tick=0.1, max_leverage=50,
                              quote_to_inr=quote_to_inr, min_notional=5.0)
    if "ETH" in pair:
        return InstrumentSpec(pair, min_qty=0.01, qty_step=0.01, tick=0.01, max_leverage=50,
                              quote_to_inr=quote_to_inr, min_notional=5.0)
    return InstrumentSpec(pair, min_qty=1.0, qty_step=1.0, tick=0.0001, max_leverage=20,
                          quote_to_inr=quote_to_inr, min_notional=5.0)
