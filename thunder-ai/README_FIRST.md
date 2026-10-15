# THUNDER AI — read this first (1 page)

**What it is.** A program that tests many small trading ideas ("sub-bots") on CoinDCX futures with **virtual
money**, measures honestly — after every fee, tax on fees, slippage and funding — whether any of them really
works on data it was not tuned on, and keeps real money out until one has proven itself.

**What it is not.** A money machine. Nobody can promise profit. "No strategy has shown a net edge yet" is a normal,
useful answer and THUNDER will say it plainly.

## Start / stop
| | Windows | Mac | Linux |
|---|---|---|---|
| Start | double-click `START_THUNDER.bat` | double-click `start_thunder.command` | `./start_thunder.sh` |
| Stop | `STOP_THUNDER.bat` | `STOP_THUNDER.command` | `./STOP_THUNDER.sh` |

You need **Python 3.11 or newer** (https://www.python.org/downloads/ — on Windows tick *Add Python to PATH*).
The first start takes a few minutes (it installs its own private copy of everything). Your browser then opens
**http://127.0.0.1:8501**. You can close the black window; THUNDER keeps running until you press Stop.
Keep the laptop **plugged in and awake** (Help page explains how).

## First run
1. A 3-step welcome asks: **demo data** (works offline, marked SAMPLE DATA) or **real CoinDCX data**.
2. Press **START** on Home. Sub-bots begin paper trading.
3. Open **Arena** → *Run / refresh the arena* (a few minutes). This is the honest scoreboard.

## The pages
Home (status, START/STOP, verdict) · Arena (ranking) · Strategy detail ("what to look for", charts, Strategy Card)
· Council (why each idea was taken or refused) · Trades · Risk & Recovery (kill-switch, Recovery Lab, why
Martingale is banned) · Insights · Backtest Lab · Live (locked) · Settings · Health · Help.

## Your money, honestly
- With **₹3,000** at 0.5% risk per trade (₹15), the assumed CoinDCX minimum order sizes make most trades
  impossible — THUNDER will show "UNDERCAPITALISED – needs ≥ ₹X". See `docs/feasibility.md` for the options.
- Live trading is **locked**. It opens only after a strategy passes the backtest gates *and* 30+ days of forward
  paper trading, you enter a trade-only API key, run a smoke test, and type a confirmation phrase.
- THUNDER **never moves money** in or out of your CoinDCX wallet.
- Tax numbers are estimates; confirm with a chartered accountant. Confirm algorithmic trading is permitted for you.

Folder with your data: `data/` (back it up). Full details: `docs/`.
