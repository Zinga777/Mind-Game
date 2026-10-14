"""Live mode — LOCKED, GATED, DELIBERATE (spec Section 17, rule H1).

UNVERIFIED_AGAINST_LIVE_EXCHANGE: written and unit-tested against the in-process
mock exchange only. CoinDCX's documentation was unreachable at build time.

Live order placement is OFF by default. There is no config switch for it: it
unlocks only when EVERY gate below passes, and every live code path calls
`require_live()` first, which raises `LiveLocked` otherwise.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from ..cards import StrategyCard, verify
from ..config.schema import Config
from ..db import kv_get, kv_set, log_event, now_ms
from ..exchanges.base import OrderRequest
from ..backtest.promotion import LIVE_ELIGIBLE, PAPER_PROVEN

CONFIRM_PHRASE = "I UNDERSTAND I CAN LOSE THIS MONEY"
FIRST_TRADES_NEEDING_APPROVAL = 20
MAX_CLOCK_SKEW_MS = 5_000


class LiveLocked(PermissionError):
    pass


@dataclass
class GateStatus:
    name: str
    passed: bool
    plain: str


def gate_status(con: sqlite3.Connection, cfg: Config, card: Optional[StrategyCard]) -> list[GateStatus]:
    g: list[GateStatus] = []
    ok_card = card is not None and card.status in (PAPER_PROVEN, LIVE_ELIGIBLE) and not card.sample_data
    hv = verify(card, cfg) if card else (False, "no card selected")
    g.append(GateStatus("Strategy is PAPER_PROVEN and its hashes verify", ok_card and hv[0],
                        "Select a Strategy Card that passed 30+ days of forward paper trading. " + hv[1]))
    last_paper = con.execute("SELECT MAX(exit_time) FROM trades WHERE mode='paper' AND strategy_id=?",
                             (card.strategy_id if card else "",)).fetchone()[0]
    fresh = bool(last_paper) and now_ms() - last_paper <= 7 * 86_400_000
    g.append(GateStatus("Paper results are less than 7 days old", fresh,
                        "The paper engine must have been running this strategy recently."))
    conn = kv_get(con, "live_conn_test", {}) or {}
    g.append(GateStatus("API key entered and read-only connection test passed", bool(conn.get("ok")),
                        "Enter a key with TRADE permission only (no withdrawal), ideally IP-bound, then press Test."))
    cap_ok = cfg.capital.allocated_live_cap_inr > 0 and cfg.risk.risk_pct <= 0.005
    in_range = True
    if card and card.validated_capital_range:
        lo, hi = card.validated_capital_range
        in_range = lo <= cfg.capital.allocated_live_cap_inr <= hi
    g.append(GateStatus("Allocated capital cap set, risk per trade <= 0.5%, inside the validated capital range",
                        cap_ok and in_range, "Set the most the bot may ever use. Outside the validated range, re-validate first."))
    g.append(GateStatus("Confirmation phrase typed", kv_get(con, "live_phrase_ok", False) is True,
                        f'Type exactly: "{CONFIRM_PHRASE}"'))
    g.append(GateStatus("Smoke test (scripts/live_smoke_test.py) logged success", bool((kv_get(con, "live_smoke_ok", {}) or {}).get("ok")),
                        "Run the smoke test once: it places a tiny far-away limit order, checks it, cancels it."))
    g.append(GateStatus("Not halted", not kv_get(con, "live_halted", False), "EXIT ALL & HALT locks live mode until reset."))
    return g


def live_enabled(con: sqlite3.Connection, cfg: Config, card: Optional[StrategyCard]) -> bool:
    return all(x.passed for x in gate_status(con, cfg, card)) and kv_get(con, "live_armed", False) is True


def require_live(con: sqlite3.Connection, cfg: Config, card: Optional[StrategyCard]) -> None:
    if not live_enabled(con, cfg, card):
        failed = [x.name for x in gate_status(con, cfg, card) if not x.passed] or ["live mode not armed"]
        raise LiveLocked("Live trading is locked: " + "; ".join(failed))


class LiveExecutor:
    """Places real orders through CoinDCXPrivate. Every method re-checks the gates."""

    def __init__(self, con: sqlite3.Connection, cfg: Config, card: StrategyCard, private, alert=None):
        self.con, self.cfg, self.card, self.ex = con, cfg, card, private
        self.alert = alert or (lambda level, msg: log_event(con, level, "live", msg))
        self.rejections = 0

    def _guard(self) -> None:
        require_live(self.con, self.cfg, self.card)
        skew = abs(self.ex.server_time_ms() - now_ms())
        if skew > MAX_CLOCK_SKEW_MS:
            raise LiveLocked(f"clock skew {skew} ms vs exchange: fix the computer clock")

    def needs_owner_approval(self) -> bool:
        n = self.con.execute("SELECT COUNT(*) FROM trades WHERE mode='live'").fetchone()[0]
        return kv_get(self.con, "live_per_trade_approval", True) and n < FIRST_TRADES_NEEDING_APPROVAL

    def equity_inr(self) -> float:
        raw = self.ex.balances()
        bal = 0.0
        for w in raw or []:
            if w.get("currency_short_name") == self.cfg.exchange.margin_currency:
                bal += float(w.get("balance", 0)) + float(w.get("unrealised_pnl", 0) or 0)
        return bal

    def open_position(self, pair: str, side: str, qty: float, stop: float, target: float, leverage: int,
                      limit_price: Optional[float] = None) -> dict:
        self._guard()
        coid = f"th-{uuid.uuid4().hex[:16]}"
        self.ex.update_leverage(pair, leverage)
        req = OrderRequest(coid, pair, "buy" if side == "long" else "sell",
                           "limit" if limit_price else "market", qty, price=limit_price, leverage=leverage)
        self.con.execute("INSERT INTO orders(mode,account_id,client_order_id,instrument,side,order_type,qty,price,status,created_at,updated_at)"
                         " VALUES('live',?,?,?,?,?,?,?,?,?,?)", (self.card.card_id, coid, pair, req.side, req.order_type,
                                                                 qty, limit_price, "sent", now_ms(), now_ms()))
        try:
            ack = self.ex.place_order(req)
        except Exception as e:
            # never blindly resend: check whether it reached the exchange first
            self.rejections += 1
            self.alert("ERROR", f"entry order failed ({type(e).__name__}); not resent")
            if self.rejections >= 3:
                self.halt("3 consecutive order rejections")
            raise
        self.rejections = 0
        self.con.execute("UPDATE orders SET exchange_order_id=?, status=?, updated_at=? WHERE client_order_id=?",
                         (ack.order_id, ack.status, now_ms(), coid))
        # protective orders immediately on fill
        pos = [p for p in self.ex.positions() if p.pair == pair]
        if not pos:
            return {"client_order_id": coid, "status": ack.status, "protected": False, "note": "not filled yet"}
        try:
            self.ex.create_tpsl(pos[0].position_id, stop, target)
        except Exception as e:
            self.alert("HALT", f"could not place stop-loss ({type(e).__name__}): exiting at market and halting")
            try:
                self.ex.exit_position(pos[0].position_id)
            finally:
                self.halt("protective order failure")
            return {"client_order_id": coid, "status": "exited", "protected": False}
        self.alert("WARN", f"LIVE order filled: {side} {qty} {pair}; stop {stop}, target {target}")
        return {"client_order_id": coid, "status": ack.status, "protected": True, "position_id": pos[0].position_id}

    def exit_all_and_halt(self, reason: str = "owner pressed EXIT ALL & HALT") -> None:
        """Cancels open orders and closes positions at market, then locks live mode.
        Deliberately does NOT require the gates: getting out must always be possible."""
        for o in self.con.execute("SELECT exchange_order_id FROM orders WHERE mode='live' AND status IN ('open','sent','untriggered')"):
            if o[0]:
                try:
                    self.ex.cancel_order(o[0])
                except Exception:
                    pass
        for p in self.ex.positions():
            try:
                self.ex.exit_position(p.position_id)
            except Exception as e:
                self.alert("ERROR", f"exit failed for {p.pair}: {type(e).__name__}")
        self.halt(reason)

    def halt(self, reason: str) -> None:
        kv_set(self.con, "live_halted", True)
        kv_set(self.con, "live_armed", False)
        self.con.execute("INSERT INTO risk_events(mode,account_id,ts,kind,detail) VALUES('live',?,?,?,?)",
                         (self.card.card_id, now_ms(), "HALT", reason))
        self.alert("HALT", f"Live trading halted: {reason}")


def connection_test(con: sqlite3.Connection, private) -> dict:
    """Read-only: balance + positions. Records the result (never the key)."""
    try:
        bal = private.balances()
        pos = private.positions()
        res = {"ok": True, "ts": now_ms(), "wallets": len(bal or []), "positions": len(pos),
               "note": "Check on CoinDCX that this key has trade permission ONLY and no withdrawal permission."}
    except Exception as e:
        res = {"ok": False, "ts": now_ms(), "error": type(e).__name__}
    kv_set(con, "live_conn_test", res)
    return res


def smoke_test(con: sqlite3.Connection, private, pair: str, far_price: float, min_qty: float) -> dict:
    """Place a minimum-size limit order far from the market, verify, cancel, verify cancel."""
    steps = []
    coid = f"smoke-{uuid.uuid4().hex[:10]}"
    try:
        ack = private.place_order(OrderRequest(coid, pair, "buy", "limit", min_qty, price=far_price))
        steps.append(("placed", True))
        st = private.order_status(ack.order_id)
        steps.append(("verified open", st.get("status") in ("open", "untriggered", "init")))
        private.cancel_order(ack.order_id)
        time.sleep(0.2)
        st2 = private.order_status(ack.order_id)
        steps.append(("verified cancelled", st2.get("status") == "cancelled"))
        ok = all(s for _, s in steps)
    except Exception as e:
        steps.append((f"error {type(e).__name__}", False))
        ok = False
    res = {"ok": ok, "ts": now_ms(), "steps": steps}
    kv_set(con, "live_smoke_ok", res)
    return res
