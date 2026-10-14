# Phase 2 — Data

**What works:** resumable, paginated downloader (≤1000 candles/call, token-bucket rate limit, exponential backoff
on 429/5xx, scrubbed logs), 1m→5m fallback if 5m is not offered, 15m/1h derived from 5m, validators (monotonic,
duplicates, gaps, OHLC sanity, negative volume, spike quarantine), data-quality report, stale-data rule (H5),
demo SAMPLE DATA with a held-back "future" that is revealed candle by candle.

**Tested:** validators, staleness, pagination and fallback against the mock exchange, rate limiter, parsers.

**Not done / not verified:** the gate "12 months of real candles stored" could not be met — CoinDCX was unreachable.
It runs automatically when you choose *real data* on a networked computer.
