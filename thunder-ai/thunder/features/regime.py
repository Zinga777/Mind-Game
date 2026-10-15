"""Transparent rules-first regime classifier.

Order of checks (first match wins):
1. HIGH_VOL_EXPANSION: ATR% percentile >= 0.90 and Bollinger width percentile >= 0.80
2. LOW_VOL_SQUEEZE:    Bollinger width percentile <= 0.15
3. TREND_UP:   ADX >= 22, EMA20 > EMA50 (5m) and 1h EMA20 > 1h EMA50, EMA50 slope > 0
4. TREND_DOWN: mirror of TREND_UP
5. RANGE:      ADX < 20
6. CHOP/UNTRADEABLE otherwise (or when inputs are missing)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TREND_UP, TREND_DOWN, RANGE = "TREND_UP", "TREND_DOWN", "RANGE"
HIGH_VOL, SQUEEZE, CHOP = "HIGH_VOL_EXPANSION", "LOW_VOL_SQUEEZE", "CHOP"
ALL = [TREND_UP, TREND_DOWN, RANGE, HIGH_VOL, SQUEEZE, CHOP]
PLAIN = {
    TREND_UP: "trending up", TREND_DOWN: "trending down", RANGE: "moving sideways in a range",
    HIGH_VOL: "very volatile (big fast moves)", SQUEEZE: "unusually quiet (a squeeze)",
    CHOP: "choppy with no clear direction",
}


def classify(f: pd.DataFrame) -> pd.Series:
    adx = f["adx"].to_numpy()
    atrp = f["atr_pct_rank"].to_numpy()
    bbw = f["bbw_rank"].to_numpy()
    e20, e50 = f["ema20"].to_numpy(), f["ema50"].to_numpy()
    h20, h50 = f["h1_ema20"].to_numpy(), f["h1_ema50"].to_numpy()
    slope = f["ema50_slope_atr"].to_numpy()
    out = np.full(len(f), CHOP, dtype=object)
    up = (adx >= 22) & (e20 > e50) & (h20 > h50) & (slope > 0)
    dn = (adx >= 22) & (e20 < e50) & (h20 < h50) & (slope < 0)
    rng = adx < 20
    out[rng] = RANGE
    out[dn] = TREND_DOWN
    out[up] = TREND_UP
    out[bbw <= 0.15] = SQUEEZE
    out[(atrp >= 0.90) & (bbw >= 0.80)] = HIGH_VOL
    missing = np.isnan(adx) | np.isnan(atrp) | np.isnan(bbw) | np.isnan(h50)
    out[missing] = CHOP
    return pd.Series(out, index=f.index)
