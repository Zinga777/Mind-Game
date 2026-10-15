# Adding a strategy (sub-bot)

1. Copy `thunder/strategies/template.py` to `thunder/strategies/s9_my_idea.py`.
2. Fill in `id`, `name`, `description_plain` (two plain sentences), `regimes_allowed`, `defaults`.
3. **Pre-register** the parameter grid in `grid` *before* looking at any results. Keep it small (≤ 6 combinations):
   every combination counts toward the trial count used to discount lucky results.
4. Write `detect(F, i)`: read only `F[...][j]` for `j <= i` (closed candles). Return `self._mk(...)` with a structural
   stop; the base class enforces the minimum stop distance and the FOMO/chase limit. Never return an order.
5. Write `checklist_plain()` — what the owner should see on a chart before this bot trades.
6. Register the class in `REGISTRY` in `thunder/strategies/__init__.py`.
7. Run `python -m pytest tests/unit/test_features.py` — the look-ahead truncation test now also covers your strategy.
8. Run the arena (dashboard → Arena → Run). It will be ranked like the others and stays `RESEARCH` until it earns more.

The desk, trade builder (costs, `RR_net ≥ 1.2`, `cost_R ≤ 0.30`), sizing and risk guard are shared; you do not
(and must not) duplicate them.
