"""Objective candlestick pattern detection from closed OHLC.

Definitions (body = |close-open|, range = high-low, upper = high-max(o,c),
lower = min(o,c)-low):
- doji: body <= 10% of range
- hammer / bullish pin: lower >= 2*body, upper <= 0.5*body (or <= 15% range), body in top third
- shooting star / bearish pin: upper >= 2*body, lower small, body in bottom third
- bullish engulfing: prev bearish, current bullish, body covers prev body
- bearish engulfing: mirror
- inside bar: high < prev high and low > prev low
- outside bar: high > prev high and low < prev low
- morning star: big bearish, small body (<30% of first), bullish closing above midpoint of first
- evening star: mirror
- three white soldiers / black crows: three consecutive bodies same direction, each closing higher/lower,
  each body >= 50% of range
- tweezer bottom/top: equal lows/highs (within 5% of range) on opposite-colour consecutive bars
- marubozu: body >= 90% of range
A pattern is only a feature; its value is judged with location and context.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    rng = np.maximum(h - l, 1e-12)
    body = np.abs(c - o)
    up = h - np.maximum(o, c)
    lo = np.minimum(o, c) - l
    bull = c > o
    bear = c < o
    sh = lambda x, k=1: np.concatenate([np.full(k, np.nan), x[:-k]])
    po, pc, ph, pl = sh(o), sh(c), sh(h), sh(l)
    pbody = np.abs(pc - po)
    out = pd.DataFrame(index=df.index)
    out["doji"] = body <= 0.1 * rng
    out["hammer"] = (lo >= 2 * body) & (up <= np.maximum(0.5 * body, 0.15 * rng)) & (np.minimum(o, c) >= l + rng * 0.6)
    out["shooting_star"] = (up >= 2 * body) & (lo <= np.maximum(0.5 * body, 0.15 * rng)) & (np.maximum(o, c) <= l + rng * 0.4)
    out["bull_engulf"] = bull & (pc < po) & (c >= po) & (o <= pc) & (body > pbody)
    out["bear_engulf"] = bear & (pc > po) & (c <= po) & (o >= pc) & (body > pbody)
    out["inside_bar"] = (h < ph) & (l > pl)
    out["outside_bar"] = (h > ph) & (l < pl)
    o2, c2 = sh(o, 2), sh(c, 2)
    b2 = np.abs(c2 - o2)
    mid2 = (o2 + c2) / 2
    out["morning_star"] = (c2 < o2) & (pbody < 0.3 * b2) & bull & (c > mid2)
    out["evening_star"] = (c2 > o2) & (pbody < 0.3 * b2) & bear & (c < mid2)
    strong = body >= 0.5 * rng
    s1, s2 = sh(strong.astype(float)), sh(strong.astype(float), 2)
    b1, bb2 = sh(bull.astype(float)), sh(bull.astype(float), 2)
    r1, r2 = sh(bear.astype(float)), sh(bear.astype(float), 2)
    out["three_soldiers"] = bull & strong & (b1 == 1) & (bb2 == 1) & (s1 == 1) & (s2 == 1) & (c > pc) & (pc > c2)
    out["three_crows"] = bear & strong & (r1 == 1) & (r2 == 1) & (s1 == 1) & (s2 == 1) & (c < pc) & (pc < c2)
    out["tweezer_bottom"] = bull & (pc < po) & (np.abs(l - pl) <= 0.05 * rng)
    out["tweezer_top"] = bear & (pc > po) & (np.abs(h - ph) <= 0.05 * rng)
    out["marubozu"] = body >= 0.9 * rng
    out = out.fillna(False).astype(bool)
    out["bull_rejection"] = out["hammer"] | out["bull_engulf"] | out["morning_star"] | out["tweezer_bottom"]
    out["bear_rejection"] = out["shooting_star"] | out["bear_engulf"] | out["evening_star"] | out["tweezer_top"]
    return out


PATTERN_COLUMNS = ["doji", "hammer", "shooting_star", "bull_engulf", "bear_engulf", "inside_bar", "outside_bar",
                   "morning_star", "evening_star", "three_soldiers", "three_crows", "tweezer_bottom",
                   "tweezer_top", "marubozu"]
