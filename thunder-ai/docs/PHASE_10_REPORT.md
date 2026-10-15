# Phase 10 — Independent audit

An independent reviewer with no prior context audited look-ahead, money maths, hard rules H1–H14, statistics,
the live lock and UI honesty. It confirmed features, strategies, desk, runner sequencing, cost/sizing maths,
H2, H8, H10, H12 and the statistics were correct, and reported these defects — **all fixed and covered by tests**:

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | HIGH | Live order size came from the paper account | Live bridge re-sizes every order from the real exchange balance, capped by the allocated cap |
| 2 | HIGH | No daily-loss stop / kill-switch on the real account; approval phase never ended | Live AccountState fed from the exchange balance enforces H7/H8 (kill-switch flattens); approvals count live fills |
| 3 | HIGH | Unfilled limit / lagging fill could leave a position without a stop | Executor waits for the fill, cancels unfilled entries, attaches TP/SL or exits + halts; unknown positions ⇒ flatten + halt |
| 4 | HIGH | EXIT ALL & HALT did not exit | Engine now cancels orders and closes positions through the executor |
| 5 | HIGH | Live could add to an open position | Refused if the exchange already holds the pair or it is expected open |
| 6 | HIGH | A card's PAPER_PROVEN status could be self-declared / imported | Status is recomputed from stored evidence; card text is never trusted |
| 7 | HIGH | Paper evidence mixed sample data / other params | Evidence uses real data only, the card's parameters, trades after the card; switching to real purges sample candles and resets paper |
| 8 | MED | Limit fill bar could book the target optimistically | On a limit fill bar only the stop can trigger |
| 9 | MED | Test-split reuse not enforced | A different version scored on the same test data ⇒ CONTAMINATED, capped at CANDIDATE |
| 10 | MED | Gates not bound to cards | Gates are in the card hash; live requires default gates |
| 11 | MED | Stale approval sent at any price | Price re-checked against the chase limit and stop before sending |
| 12 | MED | Live leverage differed from checked leverage | Live uses the leverage from its own sizing + liquidation check |
| 13 | MED | SAMPLE label global, not per row | Per-row label on Trades; sample rows purged when switching to real |
| L | LOW | Funding skipped on entry bar; unreachable clock passed the skew check; marked equity ignored fees; optimistic q-value; stale cached card | All fixed |

Not changed (informational): walk-forward results are shown but are not a promotion gate.

**Gate:** no open critical findings. 93 unit + 22 integration tests pass; `pip-audit` reports no known vulnerabilities.
