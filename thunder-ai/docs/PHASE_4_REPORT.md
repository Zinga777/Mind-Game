# Phase 4 — Backtester, costs, risk

**What works:** one bar-by-bar `StrategyRunner` used for backtest *and* paper; fee/GST/slippage/funding model;
fee-aware sizing; leverage, margin and liquidation checks; risk guard (independent of strategy code); daily loss
stop; drawdown kill-switch with typed human reset; cash-flow-aware equity, peak and time-weighted return.

**Tested (all known-answer tests from the spec pass):** Q_raw 24.2834 and 25.7597; ₹1.416 / ₹3.54 fees; RR 2.0
long and short; break-even table; never rounding up; rejection when the minimum order exceeds the budget;
₹3,000→₹15 and ₹30,000→₹150; deposit/withdrawal accounting; deposit-shock guard; UNDERCAPITALISED with the right
`min_equity_needed`; impact guard; stop-first intrabar rule; gap-through-stop fill; funding sign; limit
fill-through; cost breakdown sums to net; determinism; no hard-coded 3000 anywhere (grep test).
