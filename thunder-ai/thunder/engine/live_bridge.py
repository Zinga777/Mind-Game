"""Bridge from the shadow paper runner of the selected Strategy Card to the live executor.

UNVERIFIED_AGAINST_LIVE_EXCHANGE. Same decision code path as paper: the shadow
runner (a normal StrategyRunner on the card's instrument) decides; when it creates
a new entry order and live mode is fully unlocked, the plan is RE-SIZED from the
real exchange balance (never above the allocated cap), re-validated against the
current price, and sent. A separate live AccountState enforces the daily loss stop
(H7) and drawdown kill-switch (H8) on the REAL balance. The first 20 live trades
wait for the owner's per-trade approval.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Optional

from .. import cards as cards_mod
from ..config.schema import Config
from ..db import kv_get, kv_set, log_event, now_ms
from ..execution import reconciler
from ..execution.live import LiveExecutor, LiveLocked, live_enabled
from ..risk.killswitch import AccountState
from ..trade import sizing


class LiveBridge:
    def __init__(self, con: sqlite3.Connection, cfg: Config, card, private, shadow_runner, sleep=time.sleep):
        self.con, self.cfg, self.card, self.r = con, cfg, card, shadow_runner
        self.ex = LiveExecutor(con, cfg, card, private, sleep=sleep)
        self.private = private
        self._seen_pending: Optional[str] = None
        self._last_recon = 0.0
        self.expected: set[str] = set(kv_get(con, "live_expected_pairs", []) or [])
        st = kv_get(con, "live_account", None)
        self.acct: Optional[AccountState] = AccountState.from_dict(st) if st else None

    # -- real-balance risk state (H7/H8 on the live account) -----------------------------
    def refresh_account(self) -> Optional[AccountState]:
        try:
            eq = self.ex.equity_inr()
        except Exception as e:
            log_event(self.con, "WARN", "live", f"cannot read exchange balance ({type(e).__name__})")
            return None
        if self.acct is None:
            self.acct = AccountState(starting_equity=eq)
        a = self.acct
        a.roll_day(now_ms())
        # treat balance changes as realised P&L for the daily stop (deposits are confirmed separately by the owner)
        delta = eq - a.equity
        if abs(delta) > 1e-9:
            a.equity = eq
            a.day_realised += delta
        a.mark(eq, self.cfg.risk.max_drawdown_pct)
        kv_set(self.con, "live_account", a.to_dict())
        if a.halted:
            self.ex.exit_all_and_halt(f"live kill-switch: {a.halt_reason}")
        return a

    def _plan_ok(self, plan: dict) -> tuple[bool, str, Optional[sizing.SizeResult]]:
        a = self.refresh_account()
        if a is None:
            return False, "exchange balance unavailable", None
        if a.halted:
            return False, "live kill-switch active", None
        if a.daily_stop_hit(self.cfg.risk.daily_loss_stop_pct):
            return False, "live daily loss limit reached", None
        if plan["pair"] in self.expected:
            return False, "position already open on this pair", None
        price = ((kv_get(self.con, "market_now", {}) or {}).get(plan["pair"]) or {}).get("close")
        if price is None:
            return False, "no current price", None
        long = plan["side"] == "long"
        if (long and (price > plan["max_entry"] or price <= plan["stop"])) or \
           (not long and (price < plan["max_entry"] or price >= plan["stop"])):
            return False, "price moved past the chase limit or the stop since the decision", None
        equity = sizing.tradable_equity(a.sizing_equity(), self.cfg.capital.allocated_live_cap_inr)
        budget = sizing.risk_budget(equity, self.cfg.risk.risk_pct, 1.0, self.cfg.risk.max_risk_per_trade_inr)
        spec = self.r.spec
        slip = price * self.cfg.costs.slip_market_bps / 1e4
        entry = price + slip if long else price - slip
        size = sizing.size_position(equity=equity, budget=budget, entry=entry, stop=plan["stop"], spec=spec,
                                    f_in=self.cfg.costs.taker_fee, f_out=self.cfg.costs.taker_fee, gst=self.cfg.costs.gst,
                                    slip_out=plan["stop"] * self.cfg.costs.slip_stop_bps / 1e4,
                                    max_leverage_used=self.cfg.risk.max_leverage_used,
                                    max_fraction_of_exchange_lev=self.cfg.risk.max_fraction_of_exchange_leverage,
                                    margin_free_fraction=self.cfg.risk.margin_free_fraction, risk_pct=self.cfg.risk.risk_pct)
        if not size.ok:
            return False, size.reason, size
        if not sizing.stop_within_liq_limit(entry, plan["stop"], size.leverage, spec.maintenance_margin_rate,
                                            self.cfg.risk.stop_to_liq_max_fraction):
            return False, "stop too close to liquidation", size
        return True, "", size

    def after_step(self) -> None:
        """Call after the shadow runner processed a bar."""
        self.card = next((c for c in cards_mod.load_all(self.con) if c.card_id == self.card.card_id), self.card)
        self.ex.card = self.card
        if not live_enabled(self.con, self.cfg, self.card):
            return
        pe = self.r.pending
        if pe is not None:
            key = pe.trace.get("decision_id")
            if key and key != self._seen_pending:
                self._seen_pending = key
                plan = {"decision_id": key, "pair": self.r.spec.pair, "side": pe.direction, "stop": pe.stop,
                        "target": pe.target, "max_entry": pe.max_entry, "ts": now_ms()}
                if self.ex.needs_owner_approval():
                    kv_set(self.con, "live_pending_approval", plan)
                    log_event(self.con, "WARN", "live", f"Live trade waiting for your approval: {pe.direction} {plan['pair']}")
                else:
                    self._send(plan)
        appr = kv_get(self.con, "live_approval_decision", None)
        pend = kv_get(self.con, "live_pending_approval", None) or {}
        if appr and appr.get("decision_id") == pend.get("decision_id"):
            kv_set(self.con, "live_pending_approval", None)
            kv_set(self.con, "live_approval_decision", None)
            if appr.get("approved") and now_ms() - pend["ts"] < 5 * 60_000:
                self._send(pend)
            else:
                log_event(self.con, "INFO", "live", "Live trade not sent (rejected or approval came too late).")

    def _send(self, plan: dict) -> None:
        ok, why, size = self._plan_ok(plan)
        if not ok:
            log_event(self.con, "INFO", "live", f"Live trade not sent: {why}.")
            return
        try:
            res = self.ex.open_position(plan["pair"], plan["side"], size.qty, plan["stop"], plan["target"],
                                        int(size.leverage))
            if res.get("protected"):
                self.expected.add(plan["pair"])
                kv_set(self.con, "live_expected_pairs", sorted(self.expected))
        except LiveLocked as e:
            log_event(self.con, "WARN", "live", str(e))

    def reconcile(self, every_s: float = 10.0) -> list[str]:
        if time.time() - self._last_recon < every_s:
            return []
        self._last_recon = time.time()
        # positions that closed on the exchange (stop/target hit) are no longer expected
        try:
            open_pairs = {p.pair for p in self.private.positions()}
            gone = self.expected - open_pairs
            if gone:
                self.expected -= gone
                kv_set(self.con, "live_expected_pairs", sorted(self.expected))
        except Exception:
            pass
        self.refresh_account()
        problems = reconciler.check_live(self.con, self.private, self.expected)
        if problems:
            # unknown positions are not protected by our stops: get flat, cancel entries, halt
            self.ex.exit_all_and_halt("reconciliation mismatch: " + "; ".join(problems))
        return problems
