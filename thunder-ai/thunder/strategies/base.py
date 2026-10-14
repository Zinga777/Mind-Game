"""Strategy base class. A strategy is a plain-rules setup detector: it reads the
causal feature arrays at bar i and may return a Candidate (never an order).

To add a sub-bot: copy thunder/strategies/template.py, fill it in, and add it to
REGISTRY in thunder/strategies/__init__.py. See docs/ADDING_A_STRATEGY.md.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

Features = dict[str, np.ndarray]


@dataclass
class Candidate:
    strategy_id: str
    i: int                       # bar index of the signal (decision at this bar's close)
    direction: str               # "long" | "short"
    entry_type: str              # "market" | "limit"
    ref_price: float             # close at signal (market) or limit price
    stop: float
    target: float
    max_entry_price: float       # FOMO/chase limit (long: max; short: min)
    time_stop_bars: int
    expiry_bars: int = 1
    breakeven_at_r: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    invalidation: str = ""
    regime: str = ""


class Strategy:
    id: str = "S0"
    name: str = "base"
    description_plain: str = ""
    regimes_allowed: tuple[str, ...] = ()
    defaults: dict[str, Any] = {}
    grid: dict[str, list[Any]] = {}     # PRE-REGISTERED before any optimisation
    entry_method: str = "market"
    max_holding_bars: int = 48
    is_control: bool = False
    # Every strategy has these two checks; the trade builder enforces them
    # (together with the global config minimum, whichever is stricter).
    min_net_reward_after_costs: float = 1.2   # RR_net floor
    max_chase_distance_atr: float = 0.5       # default for params["max_chase_atr"]
    min_stop_atr_h1: float = 0.75             # stops never tighter than this many 1h ATRs

    def __init__(self, **params: Any):
        self.params = {**self.defaults, **params}

    # -- to implement ------------------------------------------------------------
    def detect(self, F: Features, i: int) -> Optional[Candidate]:
        raise NotImplementedError

    def checklist_plain(self) -> list[str]:
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------------
    @classmethod
    def param_grid(cls) -> list[dict[str, Any]]:
        if not cls.grid:
            return [dict(cls.defaults)]
        keys = list(cls.grid)
        return [{**cls.defaults, **dict(zip(keys, vals))} for vals in itertools.product(*(cls.grid[k] for k in keys))]

    @classmethod
    def trial_count(cls) -> int:
        return len(cls.param_grid())

    def regime_ok(self, F: Features, i: int) -> bool:
        return not self.regimes_allowed or F["regime"][i] in self.regimes_allowed

    def _mk(self, F: Features, i: int, direction: str, stop: float, *, target_r: float | None = None,
            target: float | None = None, entry_type: str | None = None, ref: float | None = None,
            reasons: list[str] | None = None, invalidation: str = "", breakeven_at_r: float | None = None,
            expiry_bars: int = 1) -> Optional[Candidate]:
        close, atr = F["close"][i], F["atr"][i]
        ref = close if ref is None else ref
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(stop):
            return None
        risk = (ref - stop) if direction == "long" else (stop - ref)
        if risk <= 0:
            return None
        # Minimum stop distance in 1h-ATR units: fees + slippage are a fixed % of price, so
        # stops narrower than this cannot pay for themselves (spec 10, "why cost_R matters").
        atr_h1 = F["h1_atr"][i] if "h1_atr" in F else np.nan
        min_risk = self.params.get("min_stop_atr_h1", self.min_stop_atr_h1) * atr_h1
        if np.isfinite(min_risk) and risk < min_risk:
            stop = ref - min_risk if direction == "long" else ref + min_risk
            risk = min_risk
        if target is None:
            tr = target_r if target_r is not None else self.params.get("target_r", 2.0)
            target = ref + tr * risk if direction == "long" else ref - tr * risk
        if (direction == "long" and target <= ref) or (direction == "short" and target >= ref):
            return None
        chase = self.params.get("max_chase_atr", self.max_chase_distance_atr) * atr
        return Candidate(self.id, i, direction, entry_type or self.entry_method, float(ref), float(stop),
                         float(target), float(ref + chase if direction == "long" else ref - chase),
                         int(self.params.get("time_stop_bars", self.max_holding_bars)), expiry_bars,
                         breakeven_at_r, reasons or [], invalidation, str(F["regime"][i]))


def ok(x) -> bool:
    return bool(x) and not (isinstance(x, float) and np.isnan(x))


def fin(*xs) -> bool:
    return all(np.isfinite(x) for x in xs)
