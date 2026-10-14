"""Cost maths (spec Section 10). Pure functions, all prices in quote units per unit qty."""
from __future__ import annotations

from dataclasses import dataclass


def gst_factor(gst: float) -> float:
    return 1.0 + gst


def fee(price: float, rate: float, gst: float) -> float:
    """Fee per unit quantity including GST on the fee."""
    return gst_factor(gst) * price * rate


def rr_gross(entry: float, stop: float, target: float, side: str) -> float:
    if side == "long":
        return (target - entry) / (entry - stop)
    return (entry - target) / (stop - entry)


@dataclass(frozen=True)
class TradeCosts:
    loss_per_unit: float      # L
    gain_per_unit: float      # W
    rr_gross: float
    rr_net: float
    cost_r: float
    fee_in: float
    fee_out_stop: float
    fee_out_target: float
    slip: float


def trade_costs(entry: float, stop: float, target: float, side: str,
                f_in: float, f_out: float, gst: float,
                slip_in: float = 0.0, slip_out: float = 0.0) -> TradeCosts:
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError("stop must differ from entry")
    fi = fee(entry, f_in, gst)
    fo_s = fee(stop, f_out, gst)
    fo_t = fee(target, f_out, gst)
    slip = slip_in + slip_out
    L = risk + fi + fo_s + slip
    W = abs(target - entry) - fi - fo_t - slip
    return TradeCosts(
        loss_per_unit=L, gain_per_unit=W,
        rr_gross=rr_gross(entry, stop, target, side),
        rr_net=W / L, cost_r=(fi + fo_s + slip) / risk,
        fee_in=fi, fee_out_stop=fo_s, fee_out_target=fo_t, slip=slip,
    )


def breakeven_winrate(rr: float, cost_r: float) -> float:
    """p* = (1 + cost_R) / (RR_gross + 1)."""
    return (1.0 + cost_r) / (rr + 1.0)


def round_trip_fee(notional: float, f_in: float, f_out: float, gst: float) -> float:
    return notional * (f_in + f_out) * gst_factor(gst)
