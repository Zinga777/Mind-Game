"""Template for a new sub-bot. Copy, rename, fill in, and register in __init__.py."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin


class MyStrategy(Strategy):
    id = "S9"
    name = "My strategy"
    description_plain = "One or two plain sentences: what it buys/sells and why."
    regimes_allowed = ()            # e.g. ("TREND_UP", "TREND_DOWN")
    defaults = {"stop_atr": 0.5, "target_r": 2.0, "max_chase_atr": 0.3, "time_stop_bars": 36}
    grid = {"target_r": [1.5, 2.5]}  # pre-register BEFORE looking at results

    def detect(self, F: Features, i: int) -> Candidate | None:
        if not self.regime_ok(F, i):
            return None
        # read only F[...][<= i]; never look at i+1
        return None

    def checklist_plain(self) -> list[str]:
        return ["What the owner should see on the chart before this sub-bot trades."]
