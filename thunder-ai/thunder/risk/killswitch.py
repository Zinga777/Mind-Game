"""Account state, daily loss stop (H7), drawdown kill-switch (H8) and cash-flow
accounting (spec 11.7). Deposits/withdrawals are never profit or loss.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Optional

IST_OFFSET_MS = 19_800_000
HALT_CONFIRM_PHRASE = "RESUME TRADING"


def ist_day(ts_ms: int) -> int:
    return (ts_ms + IST_OFFSET_MS) // 86_400_000


@dataclass
class AccountState:
    starting_equity: float
    equity: float = 0.0                 # realised (cash) equity
    peak: float = 0.0                   # cash-flow-adjusted peak of marked equity
    net_cash_flows: float = 0.0
    day: int = -1
    day_start_equity: float = 0.0
    day_realised: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    consecutive_losses: int = 0
    recent_r: list = field(default_factory=list)
    cooldown_until_ms: int = 0
    loss_streak_regime: str = ""
    twr: float = 1.0                    # chain-linked time-weighted return index
    twr_base: float = 0.0               # equity at start of current sub-period
    sizing_equity_override: Optional[float] = None  # deposit-shock guard
    pending_deposit: float = 0.0

    def __post_init__(self):
        if self.equity == 0.0:
            self.equity = self.starting_equity
        if self.peak == 0.0:
            self.peak = self.starting_equity
        if self.twr_base == 0.0:
            self.twr_base = self.starting_equity
        if self.day_start_equity == 0.0:
            self.day_start_equity = self.starting_equity

    # -- time ---------------------------------------------------------------------
    def roll_day(self, ts_ms: int) -> None:
        d = ist_day(ts_ms)
        if d != self.day:
            self.day = d
            self.day_start_equity = self.equity
            self.day_realised = 0.0

    # -- P&L ----------------------------------------------------------------------
    def apply_trade(self, net_pnl: float, r: float, regime: str, ts_ms: int) -> None:
        self.roll_day(ts_ms)
        self.equity += net_pnl
        self.day_realised += net_pnl
        self.recent_r = (self.recent_r + [r])[-30:]
        if net_pnl < 0:
            if self.consecutive_losses == 0:
                self.loss_streak_regime = regime
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self.mark(self.equity)

    def mark(self, marked_equity: float, max_dd: float | None = None) -> None:
        self.peak = max(self.peak, marked_equity)
        if max_dd is not None and self.drawdown(marked_equity) >= max_dd and not self.halted:
            self.halted = True
            self.halt_reason = f"equity fell {self.drawdown(marked_equity):.1%} below its peak (limit {max_dd:.0%})"

    def drawdown(self, marked_equity: float | None = None) -> float:
        e = self.equity if marked_equity is None else marked_equity
        return max(0.0, 1.0 - e / self.peak) if self.peak > 0 else 0.0

    # -- cash flows ---------------------------------------------------------------
    def apply_cash_flow(self, amount: float, ts_ms: int, deposit_shock_pct: float = 0.25,
                        confirmed: bool = True) -> None:
        """Deposit (+) or withdrawal (-). Adjusts peak and the TWR chain; never P&L."""
        self.roll_day(ts_ms)
        if self.twr_base > 0:
            self.twr *= self.equity / self.twr_base
        old_equity = self.equity
        self.equity += amount
        self.net_cash_flows += amount
        self.peak = max(self.peak + amount, 0.0)
        self.day_start_equity += amount
        self.twr_base = self.equity
        if amount > 0 and not confirmed and old_equity > 0 and amount / old_equity > deposit_shock_pct:
            # deposit-shock guard: keep sizing from the previous equity until the owner confirms
            self.sizing_equity_override = old_equity
            self.pending_deposit = amount
        elif amount < 0 and self.sizing_equity_override is not None:
            self.sizing_equity_override = min(self.sizing_equity_override, self.equity)

    def confirm_deposit(self) -> None:
        self.sizing_equity_override = None
        self.pending_deposit = 0.0

    def sizing_equity(self) -> float:
        if self.sizing_equity_override is not None:
            return min(self.sizing_equity_override, self.equity)
        return self.equity

    def time_weighted_return(self) -> float:
        return self.twr * (self.equity / self.twr_base if self.twr_base > 0 else 1.0) - 1.0

    def net_pnl(self) -> float:
        return self.equity - self.starting_equity - self.net_cash_flows

    # -- guards -------------------------------------------------------------------
    def daily_stop_hit(self, limit_pct: float) -> bool:
        return self.day_realised <= -limit_pct * self.day_start_equity

    def daily_used_fraction(self, limit_pct: float) -> float:
        lim = limit_pct * self.day_start_equity
        return max(0.0, -self.day_realised / lim) if lim > 0 else 0.0

    def human_reset(self, phrase: str) -> bool:
        if phrase.strip() != HALT_CONFIRM_PHRASE:
            return False
        self.halted = False
        self.halt_reason = ""
        self.peak = self.equity  # new reference after a deliberate human review
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AccountState":
        return cls(**d)
