"""S3 Range mean reversion."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin
from ..features.regime import RANGE


class RangeMeanReversion(Strategy):
    id = "S3"
    name = "Range mean reversion"
    description_plain = ("In a sideways market, buys near the bottom of the range (sells near the top) when a "
                         "rejection candle and RSI agree, aiming for the middle of the range.")
    regimes_allowed = (RANGE,)
    entry_method = "limit"
    defaults = {"rsi_lo": 35, "stop_atr": 0.5, "max_chase_atr": 0.2, "time_stop_bars": 96, "adx_max": 20}
    grid = {"rsi_lo": [30, 38], "stop_atr": [0.4, 0.8]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if not self.regime_ok(F, i):
            return None
        p = self.params
        c, a, r, adx = F["close"][i], F["atr"][i], F["rsi"][i], F["adx"][i]
        lo, up, mid = F["bb_lo"][i], F["bb_up"][i], F["bb_mid"][i]
        if not fin(c, a, r, adx, lo, up, mid) or adx >= p["adx_max"]:
            return None
        if F["low"][i] <= lo and r <= p["rsi_lo"] and F["bull_rejection"][i]:
            stop = F["low"][i] - p["stop_atr"] * a
            return self._mk(F, i, "long", stop, target=mid, reasons=["sideways market (low ADX)",
                            "tagged the lower band", "bullish rejection candle", f"RSI {r:.0f}"],
                            invalidation="close below the rejection low", expiry_bars=2)
        if F["high"][i] >= up and r >= 100 - p["rsi_lo"] and F["bear_rejection"][i]:
            stop = F["high"][i] + p["stop_atr"] * a
            return self._mk(F, i, "short", stop, target=mid, reasons=["sideways market (low ADX)",
                            "tagged the upper band", "bearish rejection candle", f"RSI {r:.0f}"],
                            invalidation="close above the rejection high", expiry_bars=2)
        return None

    def checklist_plain(self) -> list[str]:
        return ["The market is clearly sideways (ADX low, no trend on the higher timeframes).",
                "Price touches the edge of the range / outer Bollinger Band.",
                "A rejection candle forms there and RSI is stretched.",
                "The distance to the middle of the range is big enough to pay fees several times over.",
                "Entry is a resting limit order (cheaper maker fee); no fill means no trade."]
