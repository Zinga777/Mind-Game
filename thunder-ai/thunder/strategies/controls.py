"""Controls: C1 random entry (seeded) and C2 buy-and-hold / always-flat benchmarks."""
from __future__ import annotations

import numpy as np

from .base import Candidate, Features, Strategy, fin


class RandomEntry(Strategy):
    """C1: random direction and time, same stop/target/sizing/costs. Any real strategy must clearly beat this."""
    id = "C1"
    name = "Control: random entry"
    description_plain = "Enters at random times in a random direction with a typical stop and target. A yardstick."
    is_control = True
    defaults = {"prob": 1 / 150, "stop_atr": 1.5, "target_r": 2.0, "max_chase_atr": 0.5, "time_stop_bars": 144,
                "seed": 1}

    def __init__(self, **params):
        super().__init__(**params)
        rng = np.random.default_rng(int(self.params["seed"]))
        self._u = rng.random(2_000_000)
        self._d = rng.random(2_000_000)

    def detect(self, F: Features, i: int) -> Candidate | None:
        a = F["atr"][i]
        if not fin(a) or self._u[i % len(self._u)] >= self.params["prob"]:
            return None
        c = F["close"][i]
        if self._d[i % len(self._d)] < 0.5:
            return self._mk(F, i, "long", c - self.params["stop_atr"] * a, reasons=["random (control)"])
        return self._mk(F, i, "short", c + self.params["stop_atr"] * a, reasons=["random (control)"])

    def checklist_plain(self) -> list[str]:
        return ["This is a control. It has no edge by design."]


def buy_and_hold_curve(close: np.ndarray, equity0: float, leverage: float = 1.0) -> np.ndarray:
    """C2 benchmark: equity of holding `leverage` x equity notional from the first bar (no costs after entry)."""
    if len(close) == 0:
        return np.array([])
    return equity0 * (1 + leverage * (close / close[0] - 1))


def flat_curve(n: int, equity0: float) -> np.ndarray:
    return np.full(n, equity0)
