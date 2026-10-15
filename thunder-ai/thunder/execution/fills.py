"""Slippage and fill model for backtest and paper (spec 11.4).

- Market entry: next bar open +/- slippage (taker fee).
- Limit entry: fills only if the next bar trades THROUGH the limit by >= 1 tick (maker fee, no slippage).
- Stop exit: stop price worsened by stop slippage; if the bar gaps through the stop, fill at the worse of
  stop and open.
- Target exit: target worsened by market slippage (take-profit market order, taker).
- If one bar touches both stop and target, the STOP is assumed to have been hit first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..exchanges.base import OrderBook


@dataclass(frozen=True)
class SlippageModel:
    market_bps: float = 2.0
    stop_bps: float = 5.0
    high_vol_mult: float = 2.0
    k_atr: float = 0.0

    def slip(self, price: float, kind: str, regime: str = "", atr: float = 0.0,
             book: Optional[OrderBook] = None, qty: float = 0.0) -> float:
        """Slippage in price units for one side."""
        bps = self.stop_bps if kind == "stop" else self.market_bps
        if regime == "HIGH_VOL_EXPANSION":
            bps *= self.high_vol_mult
        fixed = price * bps / 1e4
        if book is not None and book.bids and book.asks:
            half = (book.asks[0][0] - book.bids[0][0]) / 2
            return max(half, depth_walk_impact(book, qty), self.k_atr * atr)
        return max(fixed, self.k_atr * atr)


def depth_walk_impact(book: OrderBook, qty: float, side: str = "buy") -> float:
    levels = book.asks if side == "buy" else book.bids
    if not levels or qty <= 0:
        return 0.0
    best = levels[0][0]
    left, cost = qty, 0.0
    for p, q in levels:
        take = min(left, q)
        cost += take * p
        left -= take
        if left <= 0:
            break
    if left > 0:
        return abs(levels[-1][0] - best) * 2
    return abs(cost / qty - best)


def depth_within(book: OrderBook, pct: float) -> float:
    mid = book.mid
    b = sum(q for p, q in book.bids if p >= mid * (1 - pct))
    a = sum(q for p, q in book.asks if p <= mid * (1 + pct))
    return min(a, b)


def limit_filled(direction: str, limit: float, bar_low: float, bar_high: float, tick: float) -> bool:
    if direction == "long":
        return bar_low <= limit - tick
    return bar_high >= limit + tick


def bar_exit(direction: str, stop: float, target: float, o: float, h: float, l: float,
             slip_stop: float, slip_tgt: float) -> Optional[tuple[str, float]]:
    """Return (reason, fill_price) if the bar exits the position, pessimistic ordering."""
    if direction == "long":
        if o <= stop:
            return "stop_gap", min(stop, o) - slip_stop
        if l <= stop:
            return "stop", stop - slip_stop
        if h >= target:
            return "target", target - slip_tgt
    else:
        if o >= stop:
            return "stop_gap", max(stop, o) + slip_stop
        if h >= stop:
            return "stop", stop + slip_stop
        if l <= target:
            return "target", target + slip_tgt
    return None
