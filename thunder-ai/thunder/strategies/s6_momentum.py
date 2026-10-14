"""S6 Momentum continuation."""
from __future__ import annotations

import numpy as np

from .base import Candidate, Features, Strategy, fin
from ..features.regime import HIGH_VOL, TREND_DOWN, TREND_UP


class MomentumContinuation(Strategy):
    id = "S6"
    name = "Momentum continuation"
    description_plain = ("After a strong impulse candle on big volume, waits for a shallow pause and joins the move "
                         "when it resumes — unless price has already run too far (FOMO filter).")
    regimes_allowed = (HIGH_VOL, TREND_UP, TREND_DOWN)
    defaults = {"impulse_atr": 1.5, "vol_z": 2.0, "max_retrace": 0.5, "stop_atr": 0.3, "target_r": 2.0,
                "max_chase_atr": 0.5, "time_stop_bars": 96, "breakeven_r": 1.0}
    grid = {"impulse_atr": [1.2, 2.0], "target_r": [1.5, 2.5]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 8 or not self.regime_ok(F, i):
            return None
        p = self.params
        a = F["atr"][i]
        if not fin(a):
            return None
        for j in range(i - 6, i - 1):
            bm, vz = F["body_mom"][j], F["vol_z"][j]
            if not fin(bm, vz) or vz < p["vol_z"] or abs(bm) < p["impulse_atr"]:
                continue
            lo_imp, hi_imp = F["low"][j], F["high"][j]
            size = hi_imp - lo_imp
            if bm > 0:
                pull_lo = np.min(F["low"][j + 1:i + 1])
                if (hi_imp - pull_lo) <= p["max_retrace"] * size and F["close"][i] > F["high"][i - 1] \
                        and F["close"][i] - hi_imp <= p["max_chase_atr"] * a:
                    stop = pull_lo - p["stop_atr"] * a
                    return self._mk(F, i, "long", stop, breakeven_at_r=p["breakeven_r"],
                                    reasons=["impulse candle on heavy volume", "shallow pause", "move resumed"],
                                    invalidation="pause low breaks")
            else:
                pull_hi = np.max(F["high"][j + 1:i + 1])
                if (pull_hi - lo_imp) <= p["max_retrace"] * size and F["close"][i] < F["low"][i - 1] \
                        and lo_imp - F["close"][i] <= p["max_chase_atr"] * a:
                    stop = pull_hi + p["stop_atr"] * a
                    return self._mk(F, i, "short", stop, breakeven_at_r=p["breakeven_r"],
                                    reasons=["impulse candle on heavy volume", "shallow pause", "move resumed"],
                                    invalidation="pause high breaks")
        return None

    def checklist_plain(self) -> list[str]:
        return ["A big candle (well over one ATR) on clearly heavy volume.",
                "Price pauses but gives back less than half of that candle.",
                "A candle then closes beyond the previous candle in the impulse direction.",
                "Skip it if price is already far beyond the impulse (FOMO/chasing)."]
