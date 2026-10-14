"""Bridge from the shadow paper runner of the selected Strategy Card to the live executor.

UNVERIFIED_AGAINST_LIVE_EXCHANGE. Same decision code path as paper: the shadow
runner (a normal StrategyRunner on the card's instrument) decides; when it creates
a new entry order and live mode is fully unlocked, the same plan is sent to the
exchange. The first 20 live trades wait for the owner's per-trade approval.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Optional

from ..cards import StrategyCard
from ..config.schema import Config
from ..db import kv_get, kv_set, log_event, now_ms
from ..execution import reconciler
from ..execution.live import LiveExecutor, LiveLocked, live_enabled


class LiveBridge:
    def __init__(self, con: sqlite3.Connection, cfg: Config, card: StrategyCard, private, shadow_runner):
        self.con, self.cfg, self.card, self.r = con, cfg, card, shadow_runner
        self.ex = LiveExecutor(con, cfg, card, private)
        self.private = private
        self._seen_pending: Optional[str] = None
        self._last_recon = 0.0
        self.expected: set[str] = set()

    def after_step(self) -> None:
        """Call after the shadow runner processed a bar."""
        if not live_enabled(self.con, self.cfg, self.card):
            return
        pe = self.r.pending
        if pe is not None:
            key = pe.trace.get("decision_id")
            if key and key != self._seen_pending:
                self._seen_pending = key
                plan = {"decision_id": key, "pair": self.r.spec.pair, "side": pe.direction, "qty": pe.qty,
                        "stop": pe.stop, "target": pe.target, "limit": pe.ref if pe.plan_entry_type == "limit" else None,
                        "ts": now_ms()}
                if self.ex.needs_owner_approval():
                    kv_set(self.con, "live_pending_approval", plan)
                    log_event(self.con, "WARN", "live", f"Live trade waiting for your approval: {pe.direction} {pe.qty} {plan['pair']}")
                else:
                    self._send(plan)
        appr = kv_get(self.con, "live_approval_decision", None)
        if appr and appr.get("decision_id") == (kv_get(self.con, "live_pending_approval", {}) or {}).get("decision_id"):
            plan = kv_get(self.con, "live_pending_approval")
            kv_set(self.con, "live_pending_approval", None)
            kv_set(self.con, "live_approval_decision", None)
            if appr.get("approved") and now_ms() - plan["ts"] < 5 * 60_000:
                self._send(plan)
            else:
                log_event(self.con, "INFO", "live", "Live trade not sent (rejected or approval came too late).")

    def _send(self, plan: dict) -> None:
        lev = max(1, int(self.cfg.risk.max_leverage_used))
        try:
            res = self.ex.open_position(plan["pair"], plan["side"], plan["qty"], plan["stop"], plan["target"], lev,
                                        plan.get("limit"))
            if res.get("protected"):
                self.expected.add(plan["pair"])
        except LiveLocked as e:
            log_event(self.con, "WARN", "live", str(e))

    def reconcile(self, every_s: float = 10.0) -> list[str]:
        if time.time() - self._last_recon < every_s:
            return []
        self._last_recon = time.time()
        problems = reconciler.check_live(self.con, self.private, self.expected)
        if problems:
            self.ex.halt("reconciliation mismatch: " + "; ".join(problems))
        return problems
