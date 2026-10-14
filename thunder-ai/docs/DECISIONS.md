# Decisions (made on the owner's behalf, as the spec asks)

1. **Location.** The spec says "an empty folder"; the session's repository already held another project
   (Mind Athlete). THUNDER lives entirely in `thunder-ai/` and does not touch the other project.
2. **Goal framing.** The owner asked for a "fully profitable" bot. No system can promise that, and the spec
   forbids pretending (H13). Every decision below aims at the most realistic route to *net* profit:
   cut costs, refuse trades that cannot pay their costs, require out-of-sample evidence, and keep real
   money out until an edge is proven.
3. **Minimum stop distance = 0.75 × 1-hour ATR.** On 5-minute bars, fees + GST + slippage (~0.19% of price)
   are larger than most 5m-ATR stops, so cost_R would kill every trade. The 5m clock is kept for timing,
   but stops/targets are sized off 1h volatility and holding periods extended to 8–12 h. ("Widen the
   stop/target distance rather than scalping tiny moves" — spec §10.)
4. **Maker entries where the idea allows it** (S3 range reversion, S4 candle at level): limit orders, filled only
   when price trades through by one tick. Cuts entry fee from 0.05% to 0.02%.
5. **Research capital ₹1,00,000 for measuring edge.** At ₹3,000 nothing is feasible (see `feasibility.md`), so
   the arena measures edge in R at a capital where the minimum order does not bind, and the capital-scaling
   test reports exactly what is feasible at ₹3k/10k/25k/1L/5L. Paper sub-bots still use the owner's ₹3,000
   default and honestly show "UNDERCAPITALISED – needs ≥ ₹X".
6. **Sub-bot = strategy × instrument**, each with its own ₹3,000 virtual account (18 paper accounts incl. the
   C1 control), so "one open position per account" (H6) is simple and exact.
7. **Scorecard threshold 70** kept as the spec's starting value. The scorecard's point allocations are my
   design and are *not* validated; the Insights engine reports R by score bucket so this can be tested.
8. **Controls skip the score threshold** (random by design) but keep every hard rule, costs and sizing.
9. **Validation & test.** Features are computed causally over the whole history once, so split periods can start
   trading on their first bar without leakage (proved by the truncation test). OOS = validation + test.
10. **Walk-forward** = 3-month train → 1-month test, stepping monthly, re-optimising on each train window.
11. **Neighbours (±20%)** = adjacent points of the pre-registered grid, evaluated on validation data.
12. **Multiple-testing**: Benjamini–Hochberg across all strategy × instrument permutation p-values.
13. **Feature windows in the live engine** start at a deterministic anchor (≥45 days back, aligned to 10-day blocks),
    so results never depend on when the engine was restarted (soak test proves it).
14. **Demo data**: a seeded regime-switching random walk. 180 days are history; 60 more days are held back and
    revealed one candle at a time so demo paper trading is forward, never on bars the arena used.
15. **Leverage**: exchange leverage is set to the 5× cap; exposure is controlled by the risk budget; notional/equity
    must stay ≤ 5× and the stop must sit within half of the distance to liquidation.
16. **Funding** when the real rate is unknown: 0.01% per 8 h, charged to longs (credited to shorts), plus a
    conservative expected-funding allowance in the entry cost check.
17. **LLM council model**: `claude-opus-5-5` (configurable), structured JSON output, low effort, a cache keyed by the
    evidence hash, daily call and dollar caps. Refusals and invalid output count as "no opinion", never approval.
    Off by default; the app is complete without a key.
18. **Tax estimate**: 30% of net positive gains, no loss set-off, shown separately and labelled an estimate.
19. **Dashboard**: Streamlit multipage, bound to 127.0.0.1. Remote phone viewing is documented via SSH tunnel /
    VPN only (no built-in remote login was added, so live controls are never exposed).
20. **Live trading uses exchange-side TP/SL** immediately after the entry fills; failure ⇒ market exit + HALT.
    Live P&L is not reconstructed from fills yet (see KNOWN_LIMITATIONS).
21. **Python 3.11+**: numpy is pinned to 2.3.x on 3.11 and 2.5.x on 3.12+ (2.5 dropped 3.11).
