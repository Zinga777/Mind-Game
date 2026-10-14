# Phase 3 — Features

**What works:** EMA 9/20/21/50/100/200, SMA, EMA slope (ATR-normalised), ADX/DI, RSI, Stochastic, MACD, ROC,
candle momentum, consecutive closes, ATR/ATR%, Bollinger + width percentile, realised-vol percentile, NR7/inside
bars, volume z-score, relative volume by time of day, OBV, session VWAP (UTC and IST), confirmed swing pivots
(known k bars late), support/resistance zones with touch counts, previous-day levels, round numbers, range
breakouts/failed breakouts, 14 candlestick patterns, time/session features, opening ranges, 15m/1h context using
only closed higher-timeframe bars, and the rules-first regime classifier.

**Tested:** indicator values against hand calculations, resampling, higher-timeframe alignment, pivot lag, patterns,
and the **no-look-ahead truncation test** (features *and* every strategy's signal at bar t are identical with or
without future data).
