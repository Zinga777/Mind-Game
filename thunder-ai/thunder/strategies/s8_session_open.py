"""S8 Session-open (opening range) breakout."""
from __future__ import annotations

from .base import Candidate, Features, Strategy, fin


class SessionOpenBreakout(Strategy):
    id = "S8"
    name = "Session-open breakout"
    description_plain = ("Marks the first 30 minutes of the Asia, Europe and US sessions and trades a volume-backed "
                         "close outside that opening range within the next two hours.")
    regimes_allowed = ()
    defaults = {"vol_z": 1.0, "target_r": 2.0, "max_chase_atr": 0.5, "time_stop_bars": 96, "stop_mode": "mid"}
    grid = {"vol_z": [0.5, 1.5], "target_r": [1.5, 2.5]}

    def detect(self, F: Features, i: int) -> Candidate | None:
        if i < 1:
            return None
        p = self.params
        hi, lo, c, a, vz = F["or_high"][i], F["or_low"][i], F["close"][i], F["atr"][i], F["vol_z"][i]
        if not fin(hi, lo, c, a, vz) or vz < p["vol_z"] or F["regime"][i] == "CHOP":
            return None
        mid = (hi + lo) / 2
        pc = F["close"][i - 1]
        if c > hi and pc <= hi:
            stop = mid if p["stop_mode"] == "mid" else lo
            return self._mk(F, i, "long", stop - 0.1 * a, reasons=["session opening range broken upward", "volume above normal"],
                            invalidation="back inside the opening range")
        if c < lo and pc >= lo:
            stop = mid if p["stop_mode"] == "mid" else hi
            return self._mk(F, i, "short", stop + 0.1 * a, reasons=["session opening range broken downward", "volume above normal"],
                            invalidation="back inside the opening range")
        return None

    def checklist_plain(self) -> list[str]:
        return ["Note the high and low of the first 30 minutes after 05:30, 12:30 and 18:30 IST.",
                "Within the next 2 hours, a candle closes outside that range on above-normal volume.",
                "Stop at the middle of the opening range.",
                "Skip choppy markets."]
