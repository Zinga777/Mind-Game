"""Specialist analysts (spec 9.2). Each is a deterministic function returning an
AnalystReport about a candidate, using only features at bar i (closed candles).

`confidence` is None: no analyst has a historical calibration yet, so it does not
pretend to know a probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

from ...strategies.base import Candidate, Features


@dataclass
class AnalystReport:
    analyst: str
    direction: str                     # bullish | bearish | neutral
    evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    invalidation: str = ""
    confidence: Optional[float] = None
    missing_information: list[str] = field(default_factory=list)
    points: float = 0.0                # contribution to its scorecard component (0..max)
    max_points: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _v(F: Features, k: str, i: int) -> float:
    x = F[k][i] if k in F else np.nan
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _dir(c: Candidate) -> str:
    return "bullish" if c.direction == "long" else "bearish"


def candlestick(F: Features, i: int, c: Candidate) -> AnalystReport:
    long = c.direction == "long"
    r = AnalystReport("Candlestick", "neutral", max_points=15)
    rej = F["bull_rejection"][i] if long else F["bear_rejection"][i]
    body_dir = (F["close"][i] > F["open"][i]) if long else (F["close"][i] < F["open"][i])
    names = [n for n in ("hammer", "bull_engulf", "morning_star", "tweezer_bottom") if F[n][i]] if long else \
            [n for n in ("shooting_star", "bear_engulf", "evening_star", "tweezer_top") if F[n][i]]
    if rej:
        r.direction = _dir(c); r.points = 15
        r.evidence.append(f"{'Bullish' if long else 'Bearish'} rejection ({', '.join(names)}) confirmed on close")
    elif body_dir:
        r.direction = _dir(c); r.points = 8
        r.evidence.append("Signal candle closed in the trade direction")
    else:
        r.contradictions.append("Signal candle closed against the trade")
    if F["doji"][i]:
        r.contradictions.append("Indecision candle (doji)")
        r.points = max(0, r.points - 5)
    r.invalidation = c.invalidation
    return r


def trend_structure(F: Features, i: int, c: Candidate) -> AnalystReport:
    long = c.direction == "long"
    r = AnalystReport("Trend & structure", "neutral", max_points=25)
    up, dn = bool(F["mtf_up"][i]), bool(F["mtf_dn"][i])
    adx = _v(F, "adx", i)
    pts = 0.0
    if (long and up) or (not long and dn):
        pts += 15; r.evidence.append("5m, 15m and 1h averages all aligned with the trade")
    elif (long and dn) or (not long and up):
        r.contradictions.append("Higher timeframes point the other way")
    else:
        pts += 6; r.evidence.append("Timeframes mixed")
    struct_ok = (F["hl"][i] if long else F["lh"][i])
    if struct_ok:
        pts += 5; r.evidence.append("Swing structure agrees (higher lows)" if long else "Swing structure agrees (lower highs)")
    if np.isfinite(adx):
        if adx >= 25:
            pts += 5; r.evidence.append(f"ADX {adx:.0f}: a real trend is present")
        elif adx < 18:
            r.evidence.append(f"ADX {adx:.0f}: no trend (fine for range trades)")
            if c.strategy_id in ("S3", "S7", "S4", "S5"):
                pts += 5
    r.points = min(pts, 25)
    r.direction = _dir(c) if r.points >= 12 else "neutral"
    return r


def volume_momentum(F: Features, i: int, c: Candidate) -> AnalystReport:
    long = c.direction == "long"
    r = AnalystReport("Volume & momentum", "neutral", max_points=25)  # volume 15 + momentum/vol suitability 10
    vz, rsi, mh = _v(F, "vol_z", i), _v(F, "rsi", i), _v(F, "macd_hist", i)
    pts = 0.0
    if np.isfinite(vz):
        if vz >= 1.5:
            pts += 15; r.evidence.append(f"Volume {vz:.1f}σ above normal on the signal bar")
        elif vz >= 0.5:
            pts += 9; r.evidence.append(f"Volume modestly above normal ({vz:.1f}σ)")
        elif vz < -0.5:
            pts += 2; r.contradictions.append(f"Volume below normal ({vz:.1f}σ): little participation")
        else:
            pts += 5
    else:
        r.missing_information.append("volume statistics")
    if np.isfinite(rsi):
        if (long and 40 <= rsi <= 70) or (not long and 30 <= rsi <= 60):
            pts += 5; r.evidence.append(f"RSI {rsi:.0f} supports the move without being stretched")
        elif c.strategy_id in ("S3", "S7") and ((long and rsi < 35) or (not long and rsi > 65)):
            pts += 5; r.evidence.append(f"RSI {rsi:.0f} stretched (good for a reversion)")
        else:
            r.contradictions.append(f"RSI {rsi:.0f} works against the idea")
    if np.isfinite(mh) and ((long and mh > 0) or (not long and mh < 0)):
        pts += 5; r.evidence.append("MACD momentum agrees")
    if F["price_up_vol_down"][i] and long:
        r.contradictions.append("Price rising on falling volume (divergence)")
        pts -= 3
    r.points = float(np.clip(pts, 0, 25))
    r.direction = _dir(c) if r.points >= 12 else "neutral"
    return r


def levels_liquidity(F: Features, i: int, c: Candidate) -> AnalystReport:
    long = c.direction == "long"
    r = AnalystReport("Levels / liquidity", "neutral", max_points=20)
    a = _v(F, "atr", i)
    risk = abs(c.ref_price - c.stop)
    pts = 10.0
    obstacle = _v(F, "res", i) if long else _v(F, "sup", i)
    if np.isfinite(obstacle) and np.isfinite(a) and a > 0:
        room = (obstacle - c.ref_price) if long else (c.ref_price - obstacle)
        room_atr = room / a
        reward = abs(c.target - c.ref_price)
        if 0 < room < reward * 0.6:
            pts -= 6
            r.contradictions.append(f"{'Resistance' if long else 'Support'} {room_atr:.1f} ATR away, before the target")
        else:
            pts += 4; r.evidence.append(f"Clear room to the next {'resistance' if long else 'support'} ({room_atr:.1f} ATR)")
    behind = _v(F, "sup", i) if long else _v(F, "res", i)
    if np.isfinite(behind) and risk > 0 and abs(c.ref_price - behind) <= risk:
        pts += 6; r.evidence.append("A support/resistance zone sits between entry and stop (protection)")
    rd = _v(F, "round_dist_atr", i)
    if np.isfinite(rd) and rd < 0.2:
        r.evidence.append("Sitting on a round number")
    r.missing_information.append("live order-book walls (not available in backtest)")
    r.points = float(np.clip(pts, 0, 20))
    r.direction = _dir(c) if r.points >= 10 else "neutral"
    return r


def psychology(F: Features, i: int, c: Candidate) -> AnalystReport:
    """Observable behaviour proxies only (spec 9.5). Never claims to read minds."""
    long = c.direction == "long"
    r = AnalystReport("Psychology (observable)", "neutral", max_points=0)
    a = _v(F, "atr", i)
    ext = (F["close"][i] - _v(F, "ema20", i)) / a if np.isfinite(a) and a > 0 else np.nan
    if np.isfinite(ext) and ((long and ext > 2.5) or (not long and ext < -2.5)):
        r.contradictions.append(f"Entry is {abs(ext):.1f} ATR beyond the 20 average: chasing risk (FOMO)")
    big_red = F["close"][i] < F["open"][i] and _v(F, "body_mom", i) < -2 and _v(F, "vol_z", i) > 2
    big_green = F["close"][i] > F["open"][i] and _v(F, "body_mom", i) > 2 and _v(F, "vol_z", i) > 2
    if long and big_red:
        r.contradictions.append("Buying straight into a panic candle (needs tested confirmation first)")
    if not long and big_green:
        r.contradictions.append("Selling straight into a buying climax")
    if F["failed_up"][i] or F["failed_dn"][i]:
        r.evidence.append("Breakout failure just printed (only S5 trades this)")
    vz = _v(F, "vol_z", i)
    if np.isfinite(vz) and vz > 4:
        r.evidence.append("Extreme volume: crowded move (context only)")
    return r


def execution_cost(plan_cost_r: float | None, rr_net: float | None) -> AnalystReport:
    r = AnalystReport("Execution / cost", "neutral", max_points=15)  # RR net 10 + cost/liquidity 5
    if plan_cost_r is None or rr_net is None:
        r.missing_information.append("cost estimate")
        return r
    r.evidence.append(f"Round-trip cost = {plan_cost_r:.0%} of risk; reward/risk after costs {rr_net:.2f}")
    pts = 0.0
    pts += 10 if rr_net >= 2.0 else 7 if rr_net >= 1.5 else 4 if rr_net >= 1.2 else 0
    pts += 5 if plan_cost_r <= 0.10 else 3 if plan_cost_r <= 0.2 else 1 if plan_cost_r <= 0.3 else 0
    if plan_cost_r > 0.2:
        r.contradictions.append("Costs take a large bite of the risk")
    r.points = pts
    return r


def counter_analyst(reports: list[AnalystReport], c: Candidate) -> AnalystReport:
    r = AnalystReport("Counter-analyst", "neutral", max_points=0)
    contra = [x for rep in reports for x in rep.contradictions]
    if contra:
        r.evidence.append("Strongest reason this fails: " + contra[0])
        r.contradictions = contra
    else:
        r.evidence.append("Strongest reason this fails: an ordinary random move against us — no specific warning.")
    r.direction = "bearish" if c.direction == "long" else "bullish"
    return r
