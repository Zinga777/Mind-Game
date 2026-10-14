"""Indicators vs hand-computed values, resampling, pivot lag, patterns, and the NO-LOOK-AHEAD truncation test."""
import numpy as np
import pandas as pd
import pytest

from tests.conftest import T0, TF, make_df
from thunder.data.resampler import align_htf, resample
from thunder.features import builder, candle_patterns
from thunder.features import indicators as ind
from thunder.features.structure_levels import confirmed_pivots


def test_ema_known_values():
    x = pd.Series([1, 2, 3, 4, 5], dtype=float)
    e = ind.ema(x, 3)  # alpha = 0.5, seeded with first value
    assert np.isnan(e[0]) and np.isnan(e[1])
    assert e[2] == pytest.approx(2.25)
    assert e[4] == pytest.approx(0.5 * 5 + 0.5 * (0.5 * 4 + 0.5 * 2.25))


def test_rsi_extremes_and_known():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert ind.rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    x = pd.Series([1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2], dtype=float)
    # hand-rolled Wilder recurrence (seeded with the first change): avg += (value - avg) / 14
    d = np.diff(x.to_numpy())
    up, dn = max(d[0], 0), max(-d[0], 0)
    for v in d[1:]:
        up += (max(v, 0) - up) / 14
        dn += (max(-v, 0) - dn) / 14
    assert ind.rsi(x, 14).iloc[-1] == pytest.approx(100 - 100 / (1 + up / dn))


def test_atr_known_values():
    h = pd.Series([10, 11, 12.0]); l = pd.Series([9, 10, 10.0]); c = pd.Series([9.5, 10.5, 11.0])
    tr = ind.true_range(h, l, c)
    assert list(tr) == [1.0, 1.5, 2.0]
    a = ind.atr(h, l, c, 2)
    assert a.iloc[1] == pytest.approx(0.5 * 1.5 + 0.5 * 1.0)


def test_bollinger_and_vwap():
    c = pd.Series([1.0, 2, 3, 4, 5])
    m, u, lo, w = ind.bollinger(c, 5, 2)
    sd = np.std([1, 2, 3, 4, 5])
    assert m.iloc[-1] == 3 and u.iloc[-1] == pytest.approx(3 + 2 * sd)
    t = pd.Series([0, TF, 86_400_000])
    v = ind.session_vwap(t, pd.Series([2.0, 4, 10]), pd.Series([2.0, 4, 10]), pd.Series([2.0, 4, 10]), pd.Series([1.0, 3, 1]))
    assert v.iloc[1] == pytest.approx((2 + 12) / 4) and v.iloc[2] == pytest.approx(10)  # resets on new day


def test_resample_1m_to_5m_and_incomplete_dropped():
    n = 12
    df = pd.DataFrame({"open_time": T0 + np.arange(n) * 60_000, "open": np.arange(n) + 1.0, "high": np.arange(n) + 2.0,
                       "low": np.arange(n) + 0.5, "close": np.arange(n) + 1.5, "volume": np.ones(n)})
    r = resample(df, "1m", "5m")
    assert len(r) == 2  # the last 2 one-minute bars do not make a complete 5m bar
    assert r.iloc[0].tolist() == [T0, 1.0, 6.0, 0.5, 5.5, 5.0]


def test_htf_alignment_uses_only_closed_bars():
    base = make_df(36)
    h = resample(base, "5m", "15m").assign(val=lambda d: np.arange(len(d)))
    out = align_htf(base, "5m", h, "15m", ["val"], "x_")
    # 5m bar index 2 closes exactly when the first 15m bar closes
    assert np.isnan(out["x_val"][1]) and out["x_val"][2] == 0 and out["x_val"][4] == 0 and out["x_val"][5] == 1


def test_pivot_is_known_only_k_bars_later():
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1, 1.0])
    l = h - 0.5
    ph, _ = confirmed_pivots(h, l, k=3)
    assert np.isnan(ph[:6]).all() and ph[6] == 9  # pivot at index 3 confirmed at 3 + 3


def test_patterns():
    # bar 2: small body at the top of a long lower shadow -> hammer
    df = pd.DataFrame({"open": [10, 9.0, 9.8], "high": [10.2, 9.1, 10.05], "low": [8.9, 8.0, 8.0], "close": [9.0, 8.9, 10.0]})
    p = candle_patterns.detect(df)
    assert p["hammer"][2] and not p["shooting_star"][2]
    # bar 2: bullish body fully covering the previous bearish body -> bullish engulfing
    df = pd.DataFrame({"open": [10, 9.0, 8.85], "high": [10.2, 9.1, 9.25], "low": [8.9, 8.8, 8.8], "close": [9.0, 8.9, 9.2]})
    p = candle_patterns.detect(df)
    assert p["bull_engulf"][2] and p["bull_rejection"][2]
    assert candle_patterns.detect(pd.DataFrame({"open": [1.0], "high": [1.5], "low": [0.5], "close": [1.01]}))["doji"][0]


def test_no_look_ahead_truncation():
    """Features and signals at bar t must be identical whether or not future bars exist."""
    from thunder import strategies
    from thunder.backtest.runner import features_to_arrays
    df = make_df(2600, seed=3)
    full = builder.build(df)
    Ff = features_to_arrays(full)
    rng = np.random.default_rng(0)
    cols = [c for c in full.columns if full[c].dtype != object] + ["regime", "session"]
    for t in sorted(rng.integers(400, 2599, 6)):
        part = builder.build(df.iloc[: t + 1])
        a, b = full.iloc[t], part.iloc[t]
        for c in cols:
            va, vb = a[c], b[c]
            if isinstance(va, float) and np.isnan(va):
                assert isinstance(vb, float) and np.isnan(vb), (t, c)
            else:
                assert va == pytest.approx(vb, rel=1e-9, abs=1e-12) if isinstance(va, float) else va == vb, (t, c, va, vb)
        Fp = features_to_arrays(part)
        for sid in strategies.REGISTRY:
            s1, s2 = strategies.get(sid), strategies.get(sid)
            c1, c2 = s1.detect(Ff, t), s2.detect(Fp, t)
            assert (c1 is None) == (c2 is None), (sid, t)
            if c1:
                assert (c1.direction, c1.stop, c1.target) == (c2.direction, c2.stop, c2.target)
