"""S7 VWAP reversion (range) / VWAP reclaim (trend)."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin
from ..features.regime import RANGE, TREND_DOWN, TREND_UP


class VwapStrategy(Strategy):
    id = "S7"
    name = "VWAP reversion / reclaim"
    description_plain = ("In a range, fades price stretched far from the day's volume-weighted average price (VWAP) "
                         "back toward it; in a trend, joins when price reclaims VWAP in the trend direction.")
    regimes_allowed = (RANGE, TREND_UP, TREND_DOWN)
    defaults = {"dev_atr": 2.0, "stop_atr": 0.5, "target_r": 2.0, "max_chase_atr": 0.3, "time_stop_bars": 96}
    grid = {"dev_atr": [1.5, 2.5], "stop_atr": [0.3, 0.7]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 2 or not self.regime_ok(F, i):
            return None
        p = self.params
        c, a, vw, dev = F["close"][i], F["atr"][i], F["vwap_utc"][i], F["vwap_dev_atr"][i]
        if not fin(c, a, vw, dev):
            return None
        reg = F["regime"][i]
        if reg == RANGE:
            if dev <= -p["dev_atr"] and F["bull_rejection"][i]:
                return self._mk(F, i, "long", F["low"][i] - p["stop_atr"] * a, target=vw,
                                reasons=[f"{-dev:.1f} ATR below VWAP in a range", "bullish rejection"],
                                invalidation="new low")
            if dev >= p["dev_atr"] and F["bear_rejection"][i]:
                return self._mk(F, i, "short", F["high"][i] + p["stop_atr"] * a, target=vw,
                                reasons=[f"{dev:.1f} ATR above VWAP in a range", "bearish rejection"],
                                invalidation="new high")
        pc, pvw = F["close"][i - 1], F["vwap_utc"][i - 1]
        if reg == TREND_UP and fin(pc, pvw) and pc < pvw and c > vw:
            return self._mk(F, i, "long", min(F["low"][i], F["low"][i - 1]) - p["stop_atr"] * a,
                            reasons=["uptrend", "price reclaimed VWAP"], invalidation="close back below VWAP")
        if reg == TREND_DOWN and fin(pc, pvw) and pc > pvw and c < vw:
            return self._mk(F, i, "short", max(F["high"][i], F["high"][i - 1]) + p["stop_atr"] * a,
                            reasons=["downtrend", "price lost VWAP"], invalidation="close back above VWAP")
        return None

    def checklist_plain(self) -> list[str]:
        return ["Know which market you are in: sideways (fade the stretch) or trending (join the reclaim).",
                "Sideways: price is stretched 2+ ATR from VWAP and a rejection candle appears.",
                "Trending: price crosses back over VWAP in the trend direction and closes there.",
                "VWAP resets at 00:00 UTC each day."]
