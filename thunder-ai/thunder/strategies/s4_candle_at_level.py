"""S4 Candlestick at a high-scoring level."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin
from ..features.regime import RANGE, TREND_DOWN, TREND_UP


class CandleAtLevel(Strategy):
    id = "S4"
    name = "Candlestick at level"
    description_plain = ("Trades an engulfing or pin-bar candle only when it forms at a support/resistance zone "
                         "that price has respected several times before.")
    regimes_allowed = (TREND_UP, TREND_DOWN, RANGE)
    entry_method = "limit"
    defaults = {"min_touches": 2, "max_dist_atr": 0.5, "stop_atr": 0.4, "target_r": 2.0, "max_chase_atr": 0.2,
                "time_stop_bars": 144}
    grid = {"min_touches": [2, 3], "target_r": [1.5, 2.5]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if not self.regime_ok(F, i):
            return None
        p = self.params
        a = F["atr"][i]
        if not fin(a):
            return None
        reg = F["regime"][i]
        bull = F["bull_engulf"][i] or F["hammer"][i]
        bear = F["bear_engulf"][i] or F["shooting_star"][i]
        ds, dr = F["dist_sup_atr"][i], F["dist_res_atr"][i]
        if bull and reg != TREND_DOWN and fin(ds) and ds <= p["max_dist_atr"] and F["sup_touches"][i] >= p["min_touches"]:
            stop = min(F["low"][i], F["sup"][i]) - p["stop_atr"] * a
            return self._mk(F, i, "long", stop, reasons=[f"support zone touched {int(F['sup_touches'][i])}x",
                            "bullish engulfing/pin bar on the zone"], invalidation="close below the zone",
                            expiry_bars=2)
        if bear and reg != TREND_UP and fin(dr) and dr <= p["max_dist_atr"] and F["res_touches"][i] >= p["min_touches"]:
            stop = max(F["high"][i], F["res"][i]) + p["stop_atr"] * a
            return self._mk(F, i, "short", stop, reasons=[f"resistance zone touched {int(F['res_touches'][i])}x",
                            "bearish engulfing/pin bar on the zone"], invalidation="close above the zone",
                            expiry_bars=2)
        return None

    def checklist_plain(self) -> list[str]:
        return ["A support/resistance zone that price has turned at two or more times.",
                "An engulfing or pin-bar candle forms right on that zone (within half an ATR).",
                "The bigger picture agrees (not buying support inside a strong downtrend).",
                "A candle pattern alone is never enough — location matters most."]
