"""Trade construction: candidate -> exact plan (entry, stop, target, costs). Spec Section 10."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config.schema import Config
from ..exchanges.base import InstrumentSpec
from ..execution.fills import SlippageModel
from ..strategies.base import Candidate
from .costs import TradeCosts, trade_costs


@dataclass
class TradePlan:
    candidate: Candidate
    entry: float
    stop: float
    target: float
    f_in: float
    f_out: float
    slip_in: float
    slip_out: float
    costs: TradeCosts
    funding_cost_r: float
    ok: bool
    reason: str = ""


def round_tick(x: float, tick: float, mode: str = "nearest") -> float:
    import math
    if tick <= 0:
        return x
    n = x / tick
    n = math.floor(n + 1e-9) if mode == "down" else math.ceil(n - 1e-9) if mode == "up" else round(n)
    return round(n * tick, 10)


def build(c: Candidate, spec: InstrumentSpec, cfg: Config, slip: SlippageModel, atr: float,
          min_rr_net: Optional[float] = None) -> TradePlan:
    side = c.direction
    entry = c.ref_price
    # stops placed away from price by rounding (never pulled closer to enlarge size)
    stop = round_tick(c.stop, spec.tick, "down" if side == "long" else "up")
    target = round_tick(c.target, spec.tick, "down" if side == "long" else "up")
    maker = c.entry_type == "limit"
    f_in = cfg.costs.maker_fee if maker else cfg.costs.taker_fee
    f_out = cfg.costs.taker_fee
    slip_in = 0.0 if maker else slip.slip(entry, "market", c.regime, atr)
    slip_out = slip.slip(stop, "stop", c.regime, atr)
    exp_entry = entry + slip_in if side == "long" else entry - slip_in
    try:
        tc = trade_costs(exp_entry, stop, target, side, f_in, f_out, cfg.costs.gst, 0.0, slip_out)
    except ValueError:
        return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, None, 0.0, False, "stop not placeable")  # type: ignore[arg-type]
    risk = abs(exp_entry - stop)
    if (side == "long" and stop >= exp_entry) or (side == "short" and stop <= exp_entry):
        return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, tc, 0.0, False, "stop not placeable")
    min_stop = spec.tick * 2 + 2 * slip_out
    if risk < min_stop:
        return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, tc, 0.0, False, "stop too close for tick/spread")
    # expected funding over the holding period, in R (conservative: assume we pay)
    hold_h = c.time_stop_bars * 5 / 60
    funding = exp_entry * abs(cfg.costs.funding_rate_per_interval) * (hold_h / cfg.costs.funding_interval_hours) * 0.5
    funding_r = funding / risk
    cost_r = tc.cost_r + funding_r
    rr_floor = max(cfg.risk.min_rr_net, min_rr_net or 0.0)
    rr_net = (tc.gain_per_unit - funding) / (tc.loss_per_unit + funding)
    if rr_net < rr_floor:
        return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, tc, funding_r, False,
                         f"reward too small after costs (RR net {rr_net:.2f} < {rr_floor})")
    if cost_r > cfg.risk.max_cost_r:
        return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, tc, funding_r, False,
                         f"costs eat {cost_r:.0%} of risk (max {cfg.risk.max_cost_r:.0%})")
    return TradePlan(c, entry, stop, target, f_in, f_out, slip_in, slip_out, tc, funding_r, True)
