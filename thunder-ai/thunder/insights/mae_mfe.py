"""MAE/MFE analysis -> human-reviewed suggestions (never auto-applied)."""
from __future__ import annotations

import numpy as np


def suggestions(trades: list[dict]) -> list[str]:
    if len(trades) < 30:
        return []
    out = []
    win = [t for t in trades if t["net_pnl"] > 0]
    lose = [t for t in trades if t["net_pnl"] <= 0]
    if lose:
        mfe_l = np.array([t["mfe_r"] for t in lose])
        share = float(np.mean(mfe_l >= 1.0))
        if share > 0.35:
            out.append(f"{share:.0%} of losing trades were first +1R in profit. Consider testing a break-even "
                       "move at +1R or a closer target (as a new pre-registered variant).")
    if win:
        mae_w = np.array([t["mae_r"] for t in win])
        if float(np.median(mae_w)) < 0.3:
            out.append("Winning trades rarely go against you by more than 0.3R; the stop may be wider than needed "
                       "(test a tighter-stop variant — fees permitting).")
    tgt = [t for t in trades if t["exit_reason"] == "time_stop"]
    if len(tgt) / len(trades) > 0.4:
        out.append("Over 40% of trades end on the time-stop: targets may be too ambitious for the holding period.")
    return out
