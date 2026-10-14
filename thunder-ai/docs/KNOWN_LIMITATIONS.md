# Known limitations

- **Nothing was verified against the real CoinDCX exchange.** The build machine could not reach CoinDCX.
  Endpoints, field names, fees, minimum quantities, funding and the INR conversion rate come from the spec and an
  unofficial client library. Live-trading code is marked `UNVERIFIED_AGAINST_LIVE_EXCHANGE` and was tested only
  against a mock exchange. Run `scripts/capture_fixtures.py` and `scripts/feasibility.py --live` first.
- **No real-data results yet.** The arena has only been run on SAMPLE (synthetic) data. Synthetic results say nothing
  about real markets. The 12-month real download runs from Settings → "Use real CoinDCX data".
- **₹3,000 is too small** under the assumed contract sizes: no instrument can be traded at 0.5% risk with stops
  wide enough to pay their costs (see `feasibility.md`). Expect "UNDERCAPITALISED" rejections.
- **Order-book features** (spread, depth, imbalance) are not available in backtests, so the slippage model uses fixed
  defaults (2 bps market, 5 bps stops, ×2 in high volatility). The impact guard uses candle volume, whose units on
  CoinDCX are unverified.
- **Funding history** is not downloaded; backtests charge a constant assumed rate.
- **Live P&L** is not yet rebuilt from exchange fills; live positions are protected by exchange-side stop/target
  orders and reconciled every 10 s, but the Trades page shows paper/backtest results only.
- **Scorecard weights and analyst rules** are a reasoned starting point, not validated. Analyst confidences are
  `null` until a calibration history exists.
- **LLM A/B comparison** (rules_only vs rules_plus_llm) needs an Anthropic key and cached calls; without a key the
  recommended mode stays `rules_only`.
- **Tax** figures are estimates only. Confirm the treatment of crypto futures with a chartered accountant.
- **Keep-awake** is best-effort (Windows API call / macOS `caffeinate`); follow the Help page steps.
- **Windows/macOS launchers** were written for those systems but only exercised on Linux during the build.
- **Instrument discovery**: only the instruments listed in Settings are traded. The automatic liquidity filter
  (min 24h volume, max spread) for adding further perpetuals is not implemented; add instruments by hand after
  checking their liquidity.
- **Remote (phone) viewing** is supported only through an SSH tunnel or private VPN (see `DEPLOY_VPS.md`). A
  password-protected "Enable remote access" switch was deliberately not built, so live controls are never exposed.
- **1-minute polling between candle closes** (to trigger stops earlier in paper mode) is not implemented; paper
  stops are evaluated on each closed 5m candle with the pessimistic stop-first rule. Live stops are exchange-side.
