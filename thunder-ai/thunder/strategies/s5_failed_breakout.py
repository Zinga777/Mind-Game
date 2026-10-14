"""S5 Failed breakout / liquidity sweep."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin
from ..features.regime import RANGE, TREND_DOWN, TREND_UP


class FailedBreakout(Strategy):
    id = "S5"
    name = "Failed breakout / liquidity sweep"
    description_plain = ("When price pokes beyond a prior high/low on a volume spike but closes back inside, and the "
                         "next candle confirms, trades back into the range.")
    regimes_allowed = (RANGE, TREND_UP, TREND_DOWN)
    defaults = {"vol_z": 1.5, "stop_atr": 0.3, "target_r": 2.0, "max_chase_atr": 0.4, "time_stop_bars": 96}
    grid = {"vol_z": [1.0, 2.0], "target_r": [1.5, 2.5]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 2 or not self.regime_ok(F, i):
            return None
        p = self.params
        j = i - 1
        a = F["atr"][i]
        if not fin(a, F["vol_z"][j]) or F["vol_z"][j] < p["vol_z"]:
            return None
        if F["failed_dn"][j] and F["close"][i] > F["high"][j]:
            stop = min(F["low"][j], F["low"][i]) - p["stop_atr"] * a
            return self._mk(F, i, "long", stop, reasons=["wick below the range low closed back inside",
                            "volume spike on the sweep", "next candle confirmed upward"],
                            invalidation="new low below the sweep")
        if F["failed_up"][j] and F["close"][i] < F["low"][j]:
            stop = max(F["high"][j], F["high"][i]) + p["stop_atr"] * a
            return self._mk(F, i, "short", stop, reasons=["wick above the range high closed back inside",
                            "volume spike on the sweep", "next candle confirmed downward"],
                            invalidation="new high above the sweep")
        return None

    def checklist_plain(self) -> list[str]:
        return ["Price wicks beyond a clear prior high/low but CLOSES back inside.",
                "That candle had a volume spike (stops being run).",
                "The next candle confirms by closing beyond the sweep candle.",
                "Stop goes beyond the sweep's extreme."]
