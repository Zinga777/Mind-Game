# Phase 6 — Recovery Lab

**What works:** policies A (fixed), B (capped recovery with the owner's five questions, 1% hard cap, cooldown after
4 losses), C (de-risk after 3 losses), D (Martingale — simulator-only ruin demonstration). Block-bootstrap Monte
Carlo (10,000 paths), median and 5th-percentile ending equity, kill-switch and ruin probabilities, longest losing
streak, recovery time. B is allowed only if it beats A on both median and 5th percentile without raising the
kill-switch probability by more than 2 points.

**Tested:** Martingale is not selectable anywhere (config, strategy registry, policy function); ruin arithmetic
(₹1,905 after 7 losses; ₹1,920 needed vs ₹1,095 left); vectorised lab equals the single-path reference.
