"""Data pipeline: validators, freshness (H5), parsing of documented shapes, pagination, 1m fallback, rate limiting."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import T0, TF, make_df
from thunder.data import downloader, store
from thunder.data.validators import has_gap_in_window, is_stale, validate
from thunder.exchanges.coindcx import CoinDCXPublic
from thunder.exchanges.coindcx.http import Http, HttpError, TokenBucket
from thunder.exchanges.coindcx.models import parse_candles, parse_instrument, parse_orderbook
from thunder.exchanges.mock_server import MockCoinDCX

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_validator_detects_problems():
    df = make_df(50)
    df = pd.concat([df.iloc[:20], df.iloc[25:], df.iloc[[30]]])          # gap of 5 + a duplicate
    df.loc[df.index[3], "low"] = df.loc[df.index[3], "high"] + 1          # impossible OHLC
    clean, rep = validate(df, "5m")
    assert rep.duplicates == 1 and len(rep.gaps) == 1 and rep.gaps[0][1] == 5
    assert rep.ohlc_violations == 1 and not rep.ok
    assert clean["quarantined"].sum() >= 1


def test_spike_quarantined_not_kept_silently():
    df = make_df(400)
    df.loc[300, "high"] = df.loc[300, "close"] * 1.5
    clean, rep = validate(df, "5m")
    assert int(df.loc[300, "open_time"]) in rep.outliers and clean.loc[300, "quarantined"]


def test_staleness_rule_h5():
    assert not is_stale(T0, "5m", T0 + TF + 2 * TF - 1)
    assert is_stale(T0, "5m", T0 + TF + 2 * TF + 1)
    assert is_stale(None, "5m", T0)
    assert has_gap_in_window(make_df(10).drop(index=5), "5m", 9)


def test_parse_documented_shapes():
    inst = json.loads((FIX / "instrument_B-BTC_USDT.json").read_text())
    spec = parse_instrument(inst, quote_to_inr=88)
    assert spec.min_qty == 0.001 and spec.maker_fee == pytest.approx(0.0002) and spec.taker_fee == pytest.approx(0.0005)
    assert spec.max_leverage == 50 and spec.funding_interval_hours == 8 and spec.quote_to_inr == 88
    c = parse_candles(json.loads((FIX / "candlesticks_futures.json").read_text()))
    assert c[0].open_time_ms < c[1].open_time_ms and c[0].open_time_ms > 1e12
    ob = parse_orderbook(json.loads((FIX / "orderbook_futures.json").read_text()))
    assert ob.bids[0][0] < ob.asks[0][0] and ob.spread_bps > 0


def test_download_paginates_and_falls_back_to_1m(con):
    m = MockCoinDCX(candles_5m_missing=True)
    cl = CoinDCXPublic(Http(session=m, sleep=lambda s: None), margin_currency="INR")
    now = T0 + 3 * 86_400_000 + 123_000
    rep = downloader.download(con, cl, "B-BTC_USDT", days=2, now=now)
    assert rep["source_tf"] == "1m->5m"
    df = store.load_candles(con, "B-BTC_USDT", "5m")
    assert len(df) == 2 * 288
    assert (df.open_time.diff().dropna() == TF).all()
    assert int(df.open_time.iloc[-1]) + TF <= now     # never a still-forming candle
    assert sum(1 for c in m.calls if c[1].endswith("/candlesticks")) >= 4  # paginated (<= 1000 per call)
    # resumable: a second call fetches nothing new before the next close
    downloader.download(con, cl, "B-BTC_USDT", days=2, now=now)
    assert len(store.load_candles(con, "B-BTC_USDT", "5m")) == 2 * 288


def test_http_backoff_on_429_then_error():
    m = MockCoinDCX(fail_status={"/exchange/v1/derivatives/futures/data/active_instruments": 429})
    slept = []
    h = Http(session=m, sleep=slept.append, max_retries=3)
    with pytest.raises(HttpError):
        h.request("GET", "https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments")
    assert slept[:3] == [1.0, 2.0, 4.0] or slept.count(1.0) >= 1


def test_token_bucket_limits_rate():
    t = [0.0]
    slept = []
    b = TokenBucket(5, burst=5, clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    for _ in range(10):
        b.take()
    assert t[0] == pytest.approx(1.0, abs=0.01)   # 5 burst + 5 more at 5/s


def test_demo_reveal_moves_future_bars(con):
    downloader.load_demo(con, ["B-BTC_USDT"], days=8, future_days=2)
    n0 = len(store.load_candles(con, "B-BTC_USDT", "5m"))
    assert downloader.reveal_demo(con, "B-BTC_USDT", 3) == 3
    assert len(store.load_candles(con, "B-BTC_USDT", "5m")) == n0 + 3
    assert store.is_sample(con, "B-BTC_USDT", "5m")
    _ = np
