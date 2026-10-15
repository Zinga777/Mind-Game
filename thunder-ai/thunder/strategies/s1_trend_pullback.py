"""S1 Trend pullback."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin
from ..features.regime import TREND_DOWN, TREND_UP


class TrendPullback(Strategy):
    id = "S1"
    name = "Trend pullback"
    description_plain = ("Buys a dip inside an uptrend (or sells a bounce inside a downtrend) once a candle "
                         "shows buyers (sellers) stepping back in near the 20/50 average.")
    regimes_allowed = (TREND_UP, TREND_DOWN)
    defaults = {"rsi_min": 45, "stop_atr": 0.5, "target_r": 2.0, "max_chase_atr": 0.3, "time_stop_bars": 144,
                "breakeven_r": 1.0}
    grid = {"stop_atr": [0.3, 0.6], "target_r": [1.5, 2.0, 3.0]}
    max_holding_bars = 48

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 6 or not self.regime_ok(F, i):
            return None
        p = self.params
        c, o, a = F["close"][i], F["open"][i], F["atr"][i]
        e20, e50, r, r1 = F["ema20"][i], F["ema50"][i], F["rsi"][i], F["rsi"][i - 1]
        if not fin(c, a, e20, e50, r, r1):
            return None
        if F["mtf_up"][i] and F["regime"][i] == TREND_UP:
            touched = min(F["low"][i - 3:i + 1]) <= e20 + 0.2 * a
            confirm = (F["bull_rejection"][i] or (c > o and c > e20)) and r >= p["rsi_min"] and r > r1
            if touched and confirm and c > e50:
                stop = min(F["low"][i - 5:i + 1]) - p["stop_atr"] * a
                return self._mk(F, i, "long", stop, breakeven_at_r=p["breakeven_r"],
                                reasons=["15m and 1h trend up", "pulled back to EMA20", "bullish close, RSI turning up"],
                                invalidation="close below the pullback low")
        if F["mtf_dn"][i] and F["regime"][i] == TREND_DOWN:
            touched = max(F["high"][i - 3:i + 1]) >= e20 - 0.2 * a
            confirm = (F["bear_rejection"][i] or (c < o and c < e20)) and r <= 100 - p["rsi_min"] and r < r1
            if touched and confirm and c < e50:
                stop = max(F["high"][i - 5:i + 1]) + p["stop_atr"] * a
                return self._mk(F, i, "short", stop, breakeven_at_r=p["breakeven_r"],
                                reasons=["15m and 1h trend down", "bounced to EMA20", "bearish close, RSI turning down"],
                                invalidation="close above the bounce high")
        return None

    def checklist_plain(self) -> list[str]:
        return ["The 5-minute, 15-minute and 1-hour charts all point the same way (a clear trend).",
                "Price has pulled back to the 20-period average, not collapsed through the 50.",
                "A candle closes back in the trend direction (rejection) and RSI turns with it.",
                "The stop goes just beyond the pullback's extreme plus a small volatility buffer.",
                "Skip it if price has already run away from the entry (chasing)."]
