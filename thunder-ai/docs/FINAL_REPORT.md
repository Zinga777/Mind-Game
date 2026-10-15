# THUNDER AI — final report

## 1. How to start and stop
Double-click `START_THUNDER.bat` (Windows), `start_thunder.command` (Mac) or run `./start_thunder.sh` (Linux).
The browser opens http://127.0.0.1:8501. Stop with `STOP_THUNDER.*`. Needs Python 3.11+. Details: `README_FIRST.md`.

## 2. What the arena found
**Only SAMPLE (synthetic) data could be used** — CoinDCX was unreachable from the build machine. Sample results
say nothing about real markets. On 180 days of sample data (BTC + ETH, research capital ₹1,00,000):

| Strategy | Status | OOS trades | Net expectancy | 95% CI |
|---|---|---|---|---|
| S1 Trend pullback | CANDIDATE | 200 | +0.37R | +0.17 to +0.56 |
| S2 Volume breakout | RESEARCH | 41 | +0.24R | −0.12 to +0.60 |
| S4 Candle at level | RESEARCH | 137 | −0.02R | −0.23 to +0.21 |
| S6 Momentum | RESEARCH | 11 | +0.36R | −0.34 to +1.07 |
| S7 VWAP | RESEARCH | 9 | −0.38R | −1.00 to +0.37 |
| S8 Session open | RESEARCH | 66 | +0.07R | −0.24 to +0.39 |
| S3, S5 | RESEARCH | 0 | — | (no trade passed the cost checks) |
| C1 Random control | — | ~2,900 | ≈ −0.25R | (loses after costs, as expected) |

S1 stopped at CANDIDATE because one month produced 58% of its profit and it has no forward paper trades. The sample
generator contains trending stretches, so S1 finding an edge there shows the pipeline can detect a real edge — not
that S1 works on CoinDCX. **On real data: not yet tested.** Until a strategy passes on real data, the honest status is:
*No strategy has shown a net edge yet. Keeping real money out.*

At the default ₹3,000 per sub-bot, paper sub-bots made **no trades**: every idea was rejected as UNDERCAPITALISED (see 4).

## 3. Recovery policy
**A — fixed risk.** The Recovery Lab did not find capped recovery (B) safely better. Martingale is permanently banned.

## 4. Not verified
All CoinDCX endpoints, field names, fees, minimum order sizes, funding and the INR/USDT rate for INR-margined futures
(`api_findings.md`); all live-trading behaviour (tested only on a mock exchange); Windows/macOS launchers (tested on
Linux); tax treatment. Under the *assumed* contract sizes, ₹3,000 at 0.5% risk cannot trade any instrument with a stop
wide enough to pay its costs; about ₹10,000 makes cheaper perpetuals feasible and BTC needs ~₹25,000 (`feasibility.md`).

## 5. Next steps (and what you must provide)
1. On a computer with internet: start THUNDER, choose **real CoinDCX data** (Settings or the welcome wizard).
2. Optionally run `python scripts/capture_fixtures.py` and `python scripts/feasibility.py --live` to confirm real fees and sizes.
3. Decide on paper capital (Settings): ₹3,000 will mostly show UNDERCAPITALISED; ₹10,000–₹25,000 lets the arena's
   ideas actually trade on paper. This is your decision.
4. Run the arena on real data; leave paper trading on for 30+ days.
5. Only if a card reaches PAPER_PROVEN: a CoinDCX API key with **trade permission only, no withdrawal**, the smoke
   test, and your typed confirmation. Optional: Anthropic key (LLM council), Telegram token (alerts).
6. Confirm with a chartered accountant (tax) and confirm algorithmic API trading is permitted for you.

## 6. Reminder
Backtest and paper results do not guarantee future profit. Real trading can lose the whole allocated amount.
