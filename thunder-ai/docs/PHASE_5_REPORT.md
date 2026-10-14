# Phase 5 — Strategies, arena, validation

**What works:** S1–S8 and controls C1 (random entry, seeded) and C2 (buy-and-hold / flat); pre-registered
parameter grids with trial counts; 60/20/20 chronological splits; walk-forward; costs ×1.5; remove-best-3;
neighbouring parameters; month concentration; BTC+ETH check; permutation test against C1 with
Benjamini–Hochberg correction; promotion ladder; capital-scaling test; leaderboard; Insights engine.

**Result on SAMPLE DATA:** see `FINAL_REPORT.md`. The verdict banner shows "No strategy has shown a net edge yet"
whenever nothing reaches CANDIDATE.

**Tested:** controls behave (random entry loses after costs), promotion logic with synthetic known-edge / no-edge /
over-fit cases, permutation test calibrated on a known-null (false-positive rate ≈ 5%).
