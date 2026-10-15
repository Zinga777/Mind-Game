# CoinDCX API findings (Phase 0)

**Status: NOT VERIFIED against the live exchange.** The build environment's network policy
blocked `api.coindcx.com`, `public.coindcx.com`, `docs.coindcx.com` and `coindcx.com`
(proxy answered HTTP 403 to CONNECT; web fetch reported DNS failure). Everything below
comes from (a) the spec's Section 6.2 notes and (b) the third-party, unofficial
`coindcx` 0.1.1 package on PyPI (its source and docstrings), which agree with each other.
All code that depends on these facts is marked `UNVERIFIED_AGAINST_LIVE_EXCHANGE`.

**To verify (5 minutes, on any networked computer):** `python scripts/capture_fixtures.py`
then `python scripts/feasibility.py --live`. Compare the saved `tests/fixtures/live_*.json`
with the table below and correct `thunder/exchanges/coindcx/models.py` if anything differs.

| # | Claim | Source | Status |
|---|---|---|---|
| 1 | Base URLs `https://api.coindcx.com`, `https://public.coindcx.com` | spec, PyPI client | unknown (unreachable) |
| 2 | Active instruments: `GET /exchange/v1/derivatives/futures/data/active_instruments?margin_currency_short_name[]=INR` returns a list of pair strings | spec, PyPI client | unknown |
| 3 | INR-margined futures exist (filter value `INR`) | spec, PyPI client docstring, CoinDCX marketing | unknown |
| 4 | Instrument details: `GET /exchange/v1/derivatives/futures/data/instrument?pair=B-BTC_USDT&margin_currency_short_name=INR` → `{"instrument": {...}}` with `min_quantity, quantity_increment, price_increment, max_leverage_long/short, min_notional, maker_fee, taker_fee, funding_frequency, status, kind, order_types, time_in_force_options` | PyPI client docstring | unknown |
| 5 | `maker_fee`/`taker_fee` are **percent** values (0.02 = 0.02%) | PyPI docstring ("Maker fee percentage") | unknown — parser divides by 100 |
| 6 | Fees: maker 0.02%, taker 0.05%, GST 18% on fees | spec | unknown — check your account tier |
| 7 | Trades: `GET /exchange/v1/derivatives/futures/data/trades?pair=` | spec, PyPI | unknown |
| 8 | Order book: `GET https://public.coindcx.com/market_data/v3/orderbook/{pair}-futures/50` (bids/asks as price→qty maps) | spec | unknown |
| 9 | Candles: `GET https://public.coindcx.com/market_data/candlesticks?pair=&from=&to=&resolution=&pcode=f`, **from/to in seconds**, response `{"s":"ok","data":[{open,high,low,close,volume,time}]}` | spec, PyPI | unknown |
| 10 | Futures resolutions `'1','5','60','1D'` (no documented `15`) | PyPI docstring, CoinDCX futures PDF (search snippet) | unknown — **5m is tested at runtime; falls back to 1m→5m**; 15m/1h are always derived from 5m |
| 11 | Max 1000 candles per call | spec (spot docs) | unknown — downloader requests ≤1000 per call |
| 12 | Auth: body JSON with `timestamp` (ms); `X-AUTH-SIGNATURE = HMAC-SHA256(json.dumps(body, separators=(',',':')), secret).hexdigest()`; headers `X-AUTH-APIKEY`, `X-AUTH-SIGNATURE` | spec, PyPI client source | unknown — implemented exactly so; tested vs mock |
| 13 | Create order `POST /exchange/v1/derivatives/futures/orders/create` body `{"order": {side, pair, order_type, total_quantity, price?, stop_price?, leverage?, time_in_force?, margin_currency_short_name, ...}}`; order types `market_order, limit_order, stop_limit, stop_market, take_profit_limit, take_profit_market` | PyPI client | unknown |
| 14 | List orders `POST /exchange/v1/derivatives/futures/orders` | PyPI client | unknown |
| 15 | Cancel `/orders/cancel`, positions `/positions`, exit `/positions/exit`, TP/SL `/positions/create_tpsl`, leverage `/positions/update_leverage`, wallets `/futures/wallets` | spec ("exist under …/futures/…"), names assumed | **unknown — paths after `/futures/` are our best guess** |
| 16 | Rate limit for order creation 2000 req / 60 s | PyPI docstring | unknown — we use ≤5 req/s |
| 17 | Funding interval 8 h | PyPI field `funding_frequency` | unknown — engine accrues at 00/08/16 UTC |
| 18 | Socket feed requires socket.io 2.4.0 | spec | not used; REST polling only |
| 19 | INR/USDT conversion rate for INR-margined futures | not documented in sources | unknown — configurable, default 88 |
| 20 | API terms restrict redistribution of market data | spec | dashboard bound to 127.0.0.1; notice on Help page |

Sources consulted: spec §6.2; `coindcx` 0.1.1 wheel from PyPI (`client.py`, `endpoints/futures.py`, `enums.py`);
web search results pointing to CoinDCX's own futures API PDF and docs (not openable from here).
