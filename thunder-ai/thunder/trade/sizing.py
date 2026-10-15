"""Fee-aware position sizing (spec 11.2) and capital definitions (spec 11.7).

No function here knows a default capital: every amount is passed in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..exchanges.base import InstrumentSpec
from .costs import gst_factor


def floor_to_step(q: float, step: float) -> float:
    """Round DOWN to the instrument's quantity step (never up)."""
    if step <= 0:
        return q
    n = math.floor(q / step + 1e-9)
    return round(n * step, 12)


def tradable_equity(exchange_equity: float, allocated_cap: Optional[float]) -> float:
    if allocated_cap is None:
        return exchange_equity
    return min(exchange_equity, allocated_cap)


def risk_budget(equity: float, risk_pct: float, recovery_multiplier: float = 1.0,
                max_risk_inr: Optional[float] = None, abs_cap_pct: float = 0.01) -> float:
    b = equity * risk_pct * recovery_multiplier
    b = min(b, equity * max(abs_cap_pct, risk_pct))  # recovery may never exceed 1% per trade
    if max_risk_inr is not None:
        b = min(b, max_risk_inr)
    return max(b, 0.0)


def per_unit_loss(entry: float, stop: float, f_in: float, f_out: float, gst: float,
                  slip_in: float = 0.0, slip_out: float = 0.0) -> float:
    """den = |E-S| + G(E f_in + S f_out) + slip_in + slip_out  (quote units per unit qty)."""
    return abs(entry - stop) + gst_factor(gst) * (entry * f_in + stop * f_out) + slip_in + slip_out


@dataclass(frozen=True)
class SizeResult:
    ok: bool
    qty: float
    q_raw: float
    planned_risk: float
    realised_risk: float
    notional_inr: float
    margin_inr: float
    leverage: float
    reason: str = ""
    min_equity_needed: float = 0.0


def size_position(*, equity: float, budget: float, entry: float, stop: float,
                  spec: InstrumentSpec, f_in: float, f_out: float, gst: float,
                  slip_in: float = 0.0, slip_out: float = 0.0,
                  max_leverage_used: float = 5.0, max_fraction_of_exchange_lev: float = 0.5,
                  free_margin: Optional[float] = None, margin_free_fraction: float = 0.5,
                  risk_pct: float = 0.005,
                  depth_limit_qty: Optional[float] = None) -> SizeResult:
    """Return the largest valid quantity whose all-in loss at the stop fits the budget."""
    unit_inr = spec.contract_value * spec.quote_to_inr
    den = per_unit_loss(entry, stop, f_in, f_out, gst, slip_in, slip_out) * unit_inr
    min_risk = den * spec.min_qty
    min_eq = min_risk / risk_pct if risk_pct > 0 else float("inf")
    if den <= 0 or budget <= 0:
        return SizeResult(False, 0, 0, budget, 0, 0, 0, 0, "invalid stop or zero budget", min_eq)
    q_raw = budget / den
    q = floor_to_step(q_raw, spec.qty_step)
    if depth_limit_qty is not None:
        capped = floor_to_step(depth_limit_qty, spec.qty_step)
        if q >= spec.min_qty and capped < spec.min_qty:
            return SizeResult(False, capped, q_raw, budget, 0, 0, 0, 0,
                              "impact guard: order too large for available depth/volume", min_eq)
        q = min(q, capped)
    if q < spec.min_qty:
        return SizeResult(False, q, q_raw, budget, 0, 0, 0, 0,
                          f"UNDERCAPITALISED - needs >= {min_eq:.2f}", min_eq)
    realised = q * den
    if realised > budget + 1e-9:
        return SizeResult(False, q, q_raw, budget, realised, 0, 0, 0, "rounded risk exceeds budget", min_eq)
    notional = q * entry * unit_inr
    if spec.min_notional and q * entry * spec.contract_value < spec.min_notional:
        return SizeResult(False, q, q_raw, budget, realised, notional, 0, 0,
                          "below exchange minimum notional", min_eq)
    lev_cap = min(max_leverage_used, spec.max_leverage * max_fraction_of_exchange_lev)
    lev = notional / equity if equity > 0 else float("inf")
    if lev > lev_cap:
        return SizeResult(False, q, q_raw, budget, realised, notional, 0, lev,
                          f"notional/equity {lev:.2f}x exceeds cap {lev_cap:.2f}x", min_eq)
    # The exchange leverage setting is the cap (set explicitly per position in live mode);
    # exposure is controlled by the risk budget, leverage only changes margin.
    use_lev = max(1.0, math.floor(lev_cap))
    margin = notional / use_lev
    fm = equity if free_margin is None else free_margin
    if margin > fm * margin_free_fraction:
        return SizeResult(False, q, q_raw, budget, realised, notional, margin, lev,
                          "margin required exceeds half of free margin", min_eq)
    return SizeResult(True, q, q_raw, budget, realised, notional, margin, use_lev, "", min_eq)


def liquidation_distance(leverage: float, maintenance_margin_rate: float) -> float:
    """Approximate isolated-margin liquidation distance as a fraction of entry price."""
    return max(1.0 / leverage - maintenance_margin_rate, 0.0)


def stop_within_liq_limit(entry: float, stop: float, leverage: float, mmr: float,
                          max_fraction: float = 0.5) -> bool:
    liq = liquidation_distance(leverage, mmr)
    return abs(entry - stop) / entry <= liq * max_fraction
