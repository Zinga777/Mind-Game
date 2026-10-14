"""Confirmed swing pivots, support/resistance zones and level features.

LOOK-AHEAD CONTRACT: a swing high at bar j needs k bars on its right, so it is
only *known* at bar j + k. Every output column at bar i uses pivots confirmed
at or before i.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def confirmed_pivots(h: np.ndarray, l: np.ndarray, k: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Return arrays ph_conf, pl_conf: at index i, the price of the pivot confirmed at i (else nan).

    The pivot itself is at i - k.
    """
    n = len(h)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(2 * k, n):
        j = i - k
        win_h = h[j - k:i + 1]
        win_l = l[j - k:i + 1]
        if h[j] == win_h.max() and (win_h == h[j]).sum() == 1:
            ph[i] = h[j]
        if l[j] == win_l.min() and (win_l == l[j]).sum() == 1:
            pl[i] = l[j]
    return ph, pl


def levels(df: pd.DataFrame, atr: pd.Series, k: int = 3, memory: int = 30, tol_atr: float = 0.5) -> pd.DataFrame:
    h, l, c = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    a = atr.to_numpy(float)
    n = len(df)
    ph, pl = confirmed_pivots(h, l, k)
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    res = np.full(n, np.nan); sup = np.full(n, np.nan)
    res_touch = np.zeros(n); sup_touch = np.zeros(n)
    last_ph = np.full(n, np.nan); last_pl = np.full(n, np.nan)
    prev_ph = np.full(n, np.nan); prev_pl = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(ph[i]):
            highs.append((i, ph[i])); highs = highs[-memory:]
        if not np.isnan(pl[i]):
            lows.append((i, pl[i])); lows = lows[-memory:]
        if highs:
            last_ph[i] = highs[-1][1]
            if len(highs) > 1:
                prev_ph[i] = highs[-2][1]
        if lows:
            last_pl[i] = lows[-1][1]
            if len(lows) > 1:
                prev_pl[i] = lows[-2][1]
        ai = a[i]
        if np.isnan(ai) or ai <= 0:
            continue
        pivots = [p for _, p in highs] + [p for _, p in lows]
        if not pivots:
            continue
        arr = np.array(pivots)
        above = arr[arr > c[i]]
        below = arr[arr < c[i]]
        if above.size:
            r = above.min()
            res[i] = r
            res_touch[i] = int((np.abs(arr - r) <= tol_atr * ai).sum())
        if below.size:
            s = below.max()
            sup[i] = s
            sup_touch[i] = int((np.abs(arr - s) <= tol_atr * ai).sum())
    out = pd.DataFrame(index=df.index)
    out["swing_high"] = last_ph
    out["swing_low"] = last_pl
    out["hh"] = last_ph > prev_ph
    out["hl"] = last_pl > prev_pl
    out["lh"] = last_ph < prev_ph
    out["ll"] = last_pl < prev_pl
    out["res"] = res
    out["sup"] = sup
    out["res_touches"] = res_touch
    out["sup_touches"] = sup_touch
    out["dist_res_atr"] = (res - c) / a
    out["dist_sup_atr"] = (c - sup) / a
    return out


def range_levels(df: pd.DataFrame, n: int = 48) -> pd.DataFrame:
    """Range high/low of the PREVIOUS n bars (excluding the current one)."""
    out = pd.DataFrame(index=df.index)
    out["range_high"] = df["high"].shift(1).rolling(n, min_periods=n).max()
    out["range_low"] = df["low"].shift(1).rolling(n, min_periods=n).min()
    out["breakout_up"] = df["close"] > out["range_high"]
    out["breakout_dn"] = df["close"] < out["range_low"]
    out["failed_up"] = (df["high"] > out["range_high"]) & (df["close"] < out["range_high"])
    out["failed_dn"] = (df["low"] < out["range_low"]) & (df["close"] > out["range_low"])
    return out


def prev_day_levels(df: pd.DataFrame) -> pd.DataFrame:
    day = df["open_time"] // 86_400_000
    g = df.groupby(day)
    dh, dl = g["high"].max(), g["low"].min()
    out = pd.DataFrame(index=df.index)
    out["pdh"] = day.map(dh.shift(1)).to_numpy()
    out["pdl"] = day.map(dl.shift(1)).to_numpy()
    return out


def round_number_dist(close: pd.Series, atr: pd.Series) -> pd.Series:
    mag = 10 ** np.floor(np.log10(close.clip(lower=1e-9))) / 10
    rn = (close / mag).round() * mag
    return (close - rn).abs() / atr
