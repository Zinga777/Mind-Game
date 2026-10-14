"""Causal indicators in numpy/pandas (no TA-Lib). Every value at index i uses
only rows <= i. Wilder smoothing is implemented as an EWM with alpha = 1/n."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(h, l, c, n: int = 14) -> pd.Series:
    return wilder(true_range(h, l, c), n)


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = wilder(d.clip(lower=0), n)
    dn = wilder((-d).clip(lower=0), n)
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0).where(up.notna())


def adx(h, l, c, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=h.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=h.index)
    tr = wilder(true_range(h, l, c), n)
    pdi = 100 * wilder(plus_dm, n) / tr
    mdi = 100 * wilder(minus_dm, n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx.fillna(0), n), pdi, mdi


def macd(c: pd.Series, fast=12, slow=26, sig=9):
    m = ema(c, fast) - ema(c, slow)
    s = m.ewm(span=sig, adjust=False, min_periods=sig).mean()
    return m, s, m - s


def stochastic(h, l, c, n=14, d=3):
    ll, hh = l.rolling(n).min(), h.rolling(n).max()
    k = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    return k, k.rolling(d).mean()


def roc(c: pd.Series, n=10) -> pd.Series:
    return c.pct_change(n, fill_method=None) * 100


def bollinger(c: pd.Series, n=20, k=2.0):
    m = sma(c, n)
    s = c.rolling(n, min_periods=n).std(ddof=0)
    return m, m + k * s, m - k * s, (2 * k * s) / m


def rolling_pct_rank(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=max(20, n // 10)).rank(pct=True)


def zscore_vs_median(x: pd.Series, n: int = 96) -> pd.Series:
    med = x.rolling(n, min_periods=20).median()
    mad = (x - med).abs().rolling(n, min_periods=20).median() * 1.4826
    return (x - med) / mad.replace(0, np.nan)


def obv(c: pd.Series, v: pd.Series) -> pd.Series:
    return (np.sign(c.diff().fillna(0)) * v).cumsum()


def session_vwap(open_time_ms: pd.Series, h, l, c, v, anchor_offset_ms: int = 0) -> pd.Series:
    """VWAP reset at 00:00 of the anchor clock (UTC offset 0; IST = +19_800_000 ms)."""
    day = (open_time_ms + anchor_offset_ms) // 86_400_000
    tp = (h + l + c) / 3
    pv = (tp * v).groupby(day).cumsum()
    vv = v.groupby(day).cumsum()
    return pv / vv.replace(0, np.nan)


def consecutive_closes(c: pd.Series) -> pd.Series:
    s = np.sign(c.diff().fillna(0)).to_numpy()
    out = np.zeros(len(s))
    for i in range(1, len(s)):
        if s[i] == 0:
            out[i] = 0
        elif np.sign(out[i - 1]) == s[i]:
            out[i] = out[i - 1] + s[i]
        else:
            out[i] = s[i]
    return pd.Series(out, index=c.index)
