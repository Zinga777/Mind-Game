"""Build the full causal feature frame for a 5m series with 15m/1h context."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.resampler import align_htf, resample
from ..exchanges.base import TIMEFRAME_MS
from . import candle_patterns, indicators as ind, regime, structure_levels as sl

IST_OFFSET_MS = 19_800_000
BARS_PER_DAY_5M = 288


def _htf_frame(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    out = df[["open_time"]].copy()
    out["ema20"] = ind.ema(c, 20)
    out["ema50"] = ind.ema(c, 50)
    out["rsi"] = ind.rsi(c, 14)
    out["adx"], _, _ = ind.adx(df["high"], df["low"], c, 14)
    out["atr"] = ind.atr(df["high"], df["low"], c, 14)
    out["close"] = c
    return out


def build(df5: pd.DataFrame, funding_rate: float | None = None) -> pd.DataFrame:
    """df5: closed 5m candles (open_time ms, OHLCV). Returns features indexed like df5."""
    df = df5.reset_index(drop=True).copy()
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    f = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    f["close_time"] = f["open_time"] + TIMEFRAME_MS["5m"]
    for n in (9, 20, 21, 50, 100, 200):
        f[f"ema{n}"] = ind.ema(c, n)
    f["sma20"] = ind.sma(c, 20)
    f["atr"] = ind.atr(h, l, c, 14)
    f["atr_pct"] = f["atr"] / c
    f["ema50_slope_atr"] = (f["ema50"] - f["ema50"].shift(6)) / f["atr"]
    f["ema20_slope_atr"] = (f["ema20"] - f["ema20"].shift(3)) / f["atr"]
    f["adx"], f["pdi"], f["mdi"] = ind.adx(h, l, c, 14)
    f["rsi"] = ind.rsi(c, 14)
    f["stoch_k"], f["stoch_d"] = ind.stochastic(h, l, c)
    f["macd"], f["macd_sig"], f["macd_hist"] = ind.macd(c)
    f["roc"] = ind.roc(c, 10)
    f["body_mom"] = (c - o) / f["atr"]
    f["consec"] = ind.consecutive_closes(c)
    f["bb_mid"], f["bb_up"], f["bb_lo"], f["bbw"] = ind.bollinger(c, 20, 2.0)
    month = 30 * BARS_PER_DAY_5M
    f["bbw_rank"] = ind.rolling_pct_rank(f["bbw"], month)
    f["atr_pct_rank"] = ind.rolling_pct_rank(f["atr_pct"], month)
    rv = np.log(c).diff().rolling(BARS_PER_DAY_5M, min_periods=50).std()
    f["rv_rank"] = ind.rolling_pct_rank(rv, month)
    rng_ = h - l
    f["nr7"] = rng_ <= rng_.rolling(7).min()
    f["inside"] = (h < h.shift(1)) & (l > l.shift(1))
    f["vol_z"] = ind.zscore_vs_median(v, 96)
    hour = (df["open_time"] // 3_600_000) % 24
    med_by_hour = v.groupby(hour).transform(lambda s: s.shift(1).rolling(30, min_periods=5).median())
    f["rel_vol_tod"] = v / med_by_hour
    f["obv"] = ind.obv(c, v)
    f["obv_slope"] = f["obv"].diff(12)
    f["vwap_utc"] = ind.session_vwap(df["open_time"], h, l, c, v, 0)
    f["vwap_ist"] = ind.session_vwap(df["open_time"], h, l, c, v, IST_OFFSET_MS)
    f["vwap_dev_atr"] = (c - f["vwap_utc"]) / f["atr"]
    f["price_up_vol_down"] = (c.diff(12) > 0) & (v.rolling(12).mean() < v.rolling(48).mean())
    pats = candle_patterns.detect(df)
    for col in pats.columns:
        f[col] = pats[col].to_numpy()
    lv = sl.levels(df, f["atr"], k=3)
    for col in lv.columns:
        f[col] = lv[col].to_numpy()
    rl = sl.range_levels(df, 48)
    for col in rl.columns:
        f[col] = rl[col].to_numpy()
    pdl = sl.prev_day_levels(df)
    f["pdh"], f["pdl"] = pdl["pdh"].to_numpy(), pdl["pdl"].to_numpy()
    f["round_dist_atr"] = sl.round_number_dist(c, f["atr"])
    # time features (bar open time)
    f["hour_utc"] = hour
    f["hour_ist"] = ((df["open_time"] + IST_OFFSET_MS) // 3_600_000) % 24
    f["weekday"] = ((df["open_time"] // 86_400_000) + 3) % 7  # 0=Mon
    f["session"] = np.select([hour < 7, hour < 13, hour < 16], ["ASIA", "EUROPE", "EU_US_OVERLAP"], "US")
    f["mins_since_funding"] = ((df["open_time"] // 60_000) % (8 * 60)).astype(int)
    f["funding_rate"] = funding_rate if funding_rate is not None else np.nan
    # session opening range (first 30 min of Asia 00:00, Europe 07:00, US 13:00 UTC)
    hr = hour.to_numpy()
    start_h = np.where(hr >= 13, 13, np.where(hr >= 7, 7, 0))
    day = (df["open_time"] // 86_400_000).to_numpy()
    sess_id = day * 100 + start_h
    mins_in = ((df["open_time"].to_numpy() // 60_000) % 1440) - start_h * 60
    bar_in = mins_in // 5
    in_or = bar_in < 6
    g_hi = pd.Series(np.where(in_or, h, np.nan)).groupby(sess_id).cummax()
    g_lo = pd.Series(np.where(in_or, l, np.nan)).groupby(sess_id).cummin()
    g_hi = g_hi.groupby(sess_id).ffill(); g_lo = g_lo.groupby(sess_id).ffill()
    or_ready = (bar_in >= 6) & (bar_in < 30)
    f["or_high"] = np.where(or_ready, g_hi.to_numpy(), np.nan)
    f["or_low"] = np.where(or_ready, g_lo.to_numpy(), np.nan)
    f["bars_into_session"] = bar_in
    # higher-timeframe context (only CLOSED HTF bars)
    for tf, pre in (("15m", "m15_"), ("1h", "h1_")):
        htf = _htf_frame(resample(df, "5m", tf))
        f = align_htf(f, "5m", htf, tf, ["ema20", "ema50", "rsi", "adx", "atr", "close"], pre)
    f["mtf_up"] = (f["ema20"] > f["ema50"]) & (f["m15_ema20"] > f["m15_ema50"]) & (f["h1_ema20"] > f["h1_ema50"])
    f["mtf_dn"] = (f["ema20"] < f["ema50"]) & (f["m15_ema20"] < f["m15_ema50"]) & (f["h1_ema20"] < f["h1_ema50"])
    f["regime"] = regime.classify(f)
    f["warm"] = f.index >= 300
    return f
