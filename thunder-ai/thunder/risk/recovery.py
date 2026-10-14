"""Recovery policies (spec Section 12). No sizing rule creates an edge.

A Fixed risk (default, live OK)
B Capped recovery (only if the Recovery Lab shows it beats A; never in the first live stage)
C De-risk after a losing streak
D Classic Martingale — SIMULATOR ONLY (ruin demonstration). Never selectable (H2).
"""
from __future__ import annotations

from dataclasses import dataclass

from .killswitch import AccountState

SELECTABLE = ("A", "B", "C")


@dataclass
class RecoveryDecision:
    multiplier: float
    reason: str
    cooldown_ms: int = 0


def policy_multiplier(policy: str, st: AccountState, *, regime: str = "", score: float = 0.0,
                      threshold: float = 70.0, daily_used: float = 0.0, step: float = 0.25, cap: float = 1.5,
                      live_initial_stage: bool = False) -> RecoveryDecision:
    if policy not in SELECTABLE:
        raise ValueError("Only policies A, B, C can be used for trading (H2: no Martingale).")
    k = st.consecutive_losses
    if policy == "A" or live_initial_stage:
        return RecoveryDecision(1.0, "fixed risk")
    if policy == "C":
        if k >= 3 and score < threshold + 10:
            return RecoveryDecision(0.5, f"{k} losses in a row: half size until a win or a top-quality setup")
        return RecoveryDecision(1.0, "normal size")
    # policy B: the owner's five questions must all be "yes" before any multiplier above 1.0
    if k == 0:
        return RecoveryDecision(1.0, "no losing streak")
    if k >= 4:
        return RecoveryDecision(1.0, "4 losses in a row: cooldown", cooldown_ms=2 * 3_600_000)
    rolling_ok = len(st.recent_r) >= 10 and sum(st.recent_r) / len(st.recent_r) >= 0  # still within bounds?
    regime_same = regime == st.loss_streak_regime                                       # has the regime changed?
    equity_ok = st.equity >= 0.9 * st.peak                                              # risk budget permits?
    daily_ok = daily_used < 0.5                                                         # daily stop not near
    setup_ok = score >= threshold                                                       # next setup independently valid?
    if rolling_ok and regime_same and equity_ok and daily_ok and setup_ok:
        return RecoveryDecision(min(cap, 1 + step * k), "capped recovery conditions all met")
    return RecoveryDecision(1.0, "recovery conditions not met")


def martingale_multiplier(consecutive_losses: int) -> float:
    """Classic Martingale (D). ONLY for the Recovery Lab ruin demonstration."""
    return float(2 ** consecutive_losses)


def martingale_ruin_table(base_risk: float, equity: float, n: int = 8) -> list[dict]:
    """Cumulative loss after k straight losses when doubling from base_risk."""
    rows = []
    for k in range(1, n + 1):
        cum = base_risk * (2 ** k - 1)
        nxt = base_risk * 2 ** k
        rows.append({"losses": k, "cumulative_loss": cum, "next_risk": nxt, "left": equity - cum,
                     "can_continue": equity - cum >= nxt})
    return rows
