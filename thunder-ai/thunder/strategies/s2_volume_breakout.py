"""S2 Volume breakout after a squeeze."""
from __future__ import annotations

import numpy as np

from .base import Candidate, Features, Strategy, fin
from ..features.regime import CHOP, HIGH_VOL, RANGE, SQUEEZE, TREND_DOWN, TREND_UP


class VolumeBreakout(Strategy):
    id = "S2"
    name = "Volume breakout"
    description_plain = ("After a quiet, tight period, trades the first strong close outside the recent range "
                         "when volume is clearly above normal.")
    regimes_allowed = (SQUEEZE, RANGE, TREND_UP, TREND_DOWN, HIGH_VOL, CHOP)
    defaults = {"vol_z": 2.0, "squeeze_rank": 0.25, "stop_atr": 0.3, "target_r": 2.0, "max_chase_atr": 0.6,
                "time_stop_bars": 96}
    grid = {"vol_z": [1.5, 2.5], "target_r": [1.5, 2.5]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 13:
            return None
        p = self.params
        recent_squeeze = np.nanmin(F["bbw_rank"][i - 12:i]) <= p["squeeze_rank"] if np.isfinite(F["bbw_rank"][i - 12:i]).any() else False
        if not recent_squeeze or not fin(F["vol_z"][i], F["range_high"][i], F["range_low"][i], F["atr"][i]):
            return None
        if F["vol_z"][i] < p["vol_z"]:
            return None
        a = F["atr"][i]
        mid = (F["range_high"][i] + F["range_low"][i]) / 2
        if F["breakout_up"][i]:
            stop = max(mid, F["range_high"][i] - p["stop_atr"] * a - 0.5 * a)
            return self._mk(F, i, "long", stop, reasons=["quiet squeeze just ended", "closed above range high",
                                                         f"volume {F['vol_z'][i]:.1f} sigma above normal"],
                            invalidation="close back inside the range")
        if F["breakout_dn"][i]:
            stop = min(mid, F["range_low"][i] + p["stop_atr"] * a + 0.5 * a)
            return self._mk(F, i, "short", stop, reasons=["quiet squeeze just ended", "closed below range low",
                                                          f"volume {F['vol_z'][i]:.1f} sigma above normal"],
                            invalidation="close back inside the range")
        return None

    def checklist_plain(self) -> list[str]:
        return ["The market has been unusually quiet (narrow Bollinger Bands) for the last hour.",
                "A candle CLOSES outside the 4-hour range — a wick alone does not count.",
                "Volume on that candle is well above normal for the time of day.",
                "The stop goes back inside the range; if price returns there the breakout failed.",
                "Do not chase: skip if price is already far beyond the breakout level."]
