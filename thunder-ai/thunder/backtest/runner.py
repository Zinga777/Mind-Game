"""StrategyRunner: the ONE bar-by-bar loop used by backtest AND paper trading.

Order inside a bar i (all decisions use only data <= i):
 1. Fill an entry order created at the close of bar i-1 (at bar i's open / through the limit).
 2. Manage the open position against bar i (pending time-stop exit at open, funding, stop/target with
    pessimistic stop-first ordering, MAE/MFE, break-even move).
 3. Mark equity at bar i's close; drawdown kill-switch.
 4. If flat: detect -> build -> desk -> recovery -> size -> risk guard -> order for bar i+1.
Every candidate (including rejections) is recorded with its reason.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np

from ..config.schema import Config
from ..desk import protocol
from ..desk.protocol import DISQUALIFIED, QUALIFIED, RISK_REJECTED
from ..exchanges.base import TIMEFRAME_MS, InstrumentSpec
from ..execution.fills import SlippageModel, bar_exit, limit_filled
from ..risk import guard as G
from ..risk.killswitch import AccountState
from ..risk.recovery import policy_multiplier
from ..strategies.base import Candidate, Features, Strategy
from ..trade import builder, sizing
from ..trade.costs import gst_factor

FUNDING_PERIOD_MS = 8 * 3_600_000


@dataclass
class Position:
    direction: str
    entry: float              # fill price incl. slippage
    entry_ref: float          # pre-slippage reference
    qty: float
    stop: float
    target: float
    initial_stop: float
    entry_i: int
    entry_time: int
    f_in: float
    f_out: float
    slip_in_cost: float       # INR
    fee_entry: float          # INR, ex-GST
    planned_risk: float
    realised_risk: float
    regime: str
    score: float
    time_stop_bars: int
    breakeven_at_r: Optional[float]
    strategy_id: str
    funding: float = 0.0
    mae: float = 0.0          # price units, adverse
    mfe: float = 0.0
    pending_exit: bool = False
    trace: dict = field(default_factory=dict)


@dataclass
class PendingEntry:
    plan_entry_type: str
    direction: str
    ref: float
    stop: float
    target: float
    max_entry: float
    qty: float
    planned_risk: float
    realised_risk: float
    f_in: float
    f_out: float
    slip_in: float
    expires_i: int
    regime: str
    score: float
    time_stop_bars: int
    breakeven_at_r: Optional[float]
    strategy_id: str
    trace: dict = field(default_factory=dict)


class StrategyRunner:
    def __init__(self, strategy: Strategy, spec: InstrumentSpec, cfg: Config, account: AccountState, *,
                 mode: str = "backtest", account_id: str = "", run_id: str = "",
                 slippage: Optional[SlippageModel] = None, council=None,
                 regime_validated: Callable[[str], bool] = lambda r: True,
                 cost_multiplier: float = 1.0, record_candidates: bool = True,
                 live_initial_stage: bool = False):
        self.s, self.spec, self.cfg, self.acct = strategy, spec, cfg, account
        self.mode, self.account_id, self.run_id = mode, account_id or f"{strategy.id}:{spec.pair}", run_id
        self.slip = slippage or SlippageModel(cfg.costs.slip_market_bps * cost_multiplier,
                                              cfg.costs.slip_stop_bps * cost_multiplier,
                                              cfg.costs.high_vol_slip_multiplier)
        if cost_multiplier != 1.0:
            c = cfg.costs.model_copy(update={"maker_fee": cfg.costs.maker_fee * cost_multiplier,
                                             "taker_fee": cfg.costs.taker_fee * cost_multiplier})
            self.cfg = cfg.model_copy(update={"costs": c})
        self.council = council
        self.regime_validated = regime_validated
        self.record_candidates = record_candidates
        self.live_initial_stage = live_initial_stage
        self.pos: Optional[Position] = None
        self.pending: Optional[PendingEntry] = None
        self.trades: list[dict] = []
        self.candidates: list[dict] = []
        self.equity_curve: list[tuple[int, float]] = []
        self.last_gap_i = -10_000
        self.last_i = -1  # global bar number of the last processed bar
        self.unit = spec.contract_value * spec.quote_to_inr

    # -------------------------------------------------------------------------------
    def step(self, F: Features, i: int, data_fresh: bool = True) -> None:
        """Process local row i of F. State is keyed on the GLOBAL bar number (open_time // 5m) so
        restarts and rolling feature windows never shift it."""
        ot = int(F["open_time"][i])
        tf = TIMEFRAME_MS["5m"]
        g = ot // tf
        if g <= self.last_i:
            return  # idempotent: a bar is processed once
        prev_g = self.last_i
        self.last_i = g
        close_t = ot + tf
        if prev_g >= 0 and g - prev_g != 1:
            self.last_gap_i = g
        elif i > 0 and ot - int(F["open_time"][i - 1]) != tf:
            self.last_gap_i = g
        self.acct.roll_day(ot)
        o, h, l, c = (float(F[k][i]) for k in ("open", "high", "low", "close"))
        # 1. fill pending entry
        if self.pending is not None:
            self._try_fill(F, i, g, o, h, l)
        # 2. manage position
        if self.pos is not None:
            self._manage(F, i, g, o, h, l, c, close_t)
        # 3. mark
        marked = self.acct.equity + self._unrealised(c)
        self.acct.mark(marked, self.cfg.risk.max_drawdown_pct)
        self.equity_curve.append((close_t, marked))
        # 4. look for new candidates
        if self.pos is None and self.pending is None and bool(F["warm"][i]):
            fresh = data_fresh and (g - self.last_gap_i) > 50
            self._decide(F, i, g, close_t, fresh)

    # -------------------------------------------------------------------------------
    def _unrealised(self, price: float) -> float:
        p = self.pos
        if p is None:
            return 0.0
        sgn = 1 if p.direction == "long" else -1
        return (price - p.entry) * sgn * p.qty * self.unit - p.funding

    def _try_fill(self, F: Features, i: int, g: int, o: float, h: float, l: float) -> None:
        pe = self.pending
        long = pe.direction == "long"
        filled_px = None
        slip_px = 0.0
        if pe.plan_entry_type == "market":
            chase_bad = (o > pe.max_entry) if long else (o < pe.max_entry)
            gap_through_stop = (o <= pe.stop) if long else (o >= pe.stop)
            if chase_bad or gap_through_stop:
                self._log_cand_update(pe, "expired: price ran past the chase limit at the open")
                self.pending = None
                return
            slip_px = self.slip.slip(o, "market", pe.regime, float(F["atr"][i]))
            filled_px = o + slip_px if long else o - slip_px
            ref = o
        else:
            if limit_filled(pe.direction, pe.ref, l, h, self.spec.tick):
                filled_px = ref = pe.ref
                if (long and o < pe.ref) or (not long and o > pe.ref):
                    filled_px = ref = o  # opened through the limit: filled at the better open
            elif g >= pe.expires_i:
                self._log_cand_update(pe, "limit order not filled before expiry")
                self.pending = None
                return
            else:
                return
        risk_px = abs(filled_px - pe.stop)
        if (long and filled_px <= pe.stop) or (not long and filled_px >= pe.stop):
            self.pending = None
            return
        fee_entry = filled_px * pe.f_in * pe.qty * self.unit
        self.pos = Position(pe.direction, filled_px, ref, pe.qty, pe.stop, pe.target, pe.stop, g,
                            int(F["open_time"][i]), pe.f_in, pe.f_out, slip_px * pe.qty * self.unit, fee_entry,
                            pe.planned_risk, pe.realised_risk, pe.regime, pe.score, pe.time_stop_bars,
                            pe.breakeven_at_r, pe.strategy_id, trace=pe.trace)
        _ = risk_px
        self.pending = None

    def _manage(self, F: Features, i: int, g: int, o: float, h: float, l: float, c: float, close_t: int) -> None:
        p = self.pos
        long = p.direction == "long"
        atr = float(F["atr"][i]) if np.isfinite(F["atr"][i]) else 0.0
        if p.pending_exit:
            s = self.slip.slip(o, "market", p.regime, atr)
            self._close(g, (o - s) if long else (o + s), o, "time_stop", close_t - TIMEFRAME_MS["5m"])
            return
        # funding at 00/08/16 UTC within this bar (open_time < t <= close)
        ot = close_t - TIMEFRAME_MS["5m"]
        nxt = (ot // FUNDING_PERIOD_MS + 1) * FUNDING_PERIOD_MS
        if ot < nxt <= close_t and g > p.entry_i:
            rate = float(F["funding_rate"][i]) if np.isfinite(F["funding_rate"][i]) else self.cfg.costs.funding_rate_per_interval
            p.funding += (1 if long else -1) * rate * o * p.qty * self.unit
        ss = self.slip.slip(p.stop, "stop", p.regime, atr)
        st = self.slip.slip(p.target, "market", p.regime, atr)
        ex = bar_exit(p.direction, p.stop, p.target, o if g > p.entry_i else p.entry_ref, h, l, ss, st)
        # MAE / MFE (price units)
        adverse = (p.entry - l) if long else (h - p.entry)
        favour = (h - p.entry) if long else (p.entry - l)
        p.mae, p.mfe = max(p.mae, adverse), max(p.mfe, favour)
        if ex is not None:
            reason, px = ex
            ref = p.stop if reason.startswith("stop") else p.target
            if reason == "stop_gap":
                ref = min(p.stop, o) if long else max(p.stop, o)
            if reason.startswith("stop") and p.stop != p.initial_stop:
                reason = "breakeven_stop" if abs(p.stop - p.entry) < abs(p.initial_stop - p.entry) * 0.5 else reason
            self._close(g, px, ref, reason, close_t)
            return
        # break-even move after +X R (strategy-declared; stops only move toward profit)
        r_px = abs(p.entry - p.initial_stop)
        if p.breakeven_at_r and r_px > 0:
            fav_close = (c - p.entry) if long else (p.entry - c)
            if fav_close >= p.breakeven_at_r * r_px:
                be = p.entry + (2 * p.entry * p.f_out if long else -2 * p.entry * p.f_out)
                if (long and be > p.stop) or (not long and be < p.stop):
                    p.stop = be
        if g - p.entry_i + 1 >= p.time_stop_bars:
            p.pending_exit = True

    def _close(self, g: int, px: float, ref: float, reason: str, t: int) -> None:
        p = self.pos
        long = p.direction == "long"
        sgn = 1 if long else -1
        u = self.unit
        gross = (ref - p.entry_ref) * sgn * p.qty * u
        slip_exit = abs(ref - px) * p.qty * u
        fee_exit = px * p.f_out * p.qty * u
        fees_ex = p.fee_entry + fee_exit
        gst = fees_ex * self.cfg.costs.gst
        slippage = p.slip_in_cost + slip_exit
        net = gross - p.fee_entry - fee_exit - gst - slippage - p.funding
        r = net / p.realised_risk if p.realised_risk > 0 else 0.0
        r_px = abs(p.entry - p.initial_stop) or 1e-12
        tr = {
            "mode": self.mode, "run_id": self.run_id, "account_id": self.account_id, "strategy_id": p.strategy_id,
            "instrument": self.spec.pair, "side": p.direction, "entry_time": p.entry_time, "exit_time": t,
            "entry": p.entry, "exit": px, "qty": p.qty, "stop": p.initial_stop, "target": p.target,
            "exit_reason": reason, "gross_pnl": gross, "fee_entry": p.fee_entry, "fee_exit": fee_exit, "gst": gst,
            "slippage": slippage, "funding": p.funding, "net_pnl": net, "r_multiple": r,
            "planned_risk": p.planned_risk, "realised_risk": p.realised_risk, "regime": p.regime, "score": p.score,
            "mae_r": p.mae / r_px, "mfe_r": p.mfe / r_px, "bars_held": g - p.entry_i + 1,
            "features": p.trace.get("features", {}), "trace": {k: v for k, v in p.trace.items() if k != "features"},
        }
        self.trades.append(tr)
        self.acct.apply_trade(net, r, p.regime, t)
        self.pos = None

    # -------------------------------------------------------------------------------
    def _decide(self, F: Features, i: int, g: int, close_t: int, fresh: bool) -> None:
        cand = self.s.detect(F, i)
        if cand is None:
            return
        cfg = self.cfg
        atr = float(F["atr"][i])
        plan = builder.build(cand, self.spec, cfg, self.slip, atr, self.s.min_net_reward_after_costs)
        # controls (C1) are random by design: they skip the score threshold but not the hard rules
        threshold = 0 if self.s.is_control else cfg.council.threshold
        desk = protocol.evaluate(F, i, cand, plan, threshold,
                                 regime_validated=self.regime_validated(cand.regime), data_ok=fresh)
        rec = {"candle_close_time": close_t, "direction": cand.direction, "regime": cand.regime,
               "state": desk.state, "reason": desk.reason, "score": desk.score, "components": desk.components,
               "reports": desk.reports, "challenge": desk.challenge, "reasons": cand.reasons,
               "strategy_id": cand.strategy_id, "instrument": self.spec.pair, "entry": cand.ref_price,
               "stop": cand.stop, "target": cand.target}
        if desk.state != QUALIFIED:
            self._record(rec)
            return
        # LLM council (optional): can only veto or reduce (H10)
        llm_verdict, size_factor = None, 1.0
        if self.council is not None:
            packet = {"strategy": cand.strategy_id, "direction": cand.direction, "regime": cand.regime,
                      "score": desk.score, "components": desk.components, "reports": desk.reports,
                      "rr_net": plan.costs.rr_net, "cost_r": plan.costs.cost_r}
            out = self.council.review(packet)
            llm_verdict, size_factor = out.verdict, min(1.0, out.size_factor)
            rec["llm"] = {"verdict": out.verdict, "size_factor": size_factor, "key_risk": out.key_risk}
        # recovery multiplier + sizing
        acct = self.acct
        rd = policy_multiplier(cfg.risk.recovery_policy, acct, regime=cand.regime, score=desk.score,
                               threshold=cfg.council.threshold,
                               daily_used=acct.daily_used_fraction(cfg.risk.daily_loss_stop_pct),
                               live_initial_stage=self.live_initial_stage)
        if rd.cooldown_ms:
            acct.cooldown_until_ms = max(acct.cooldown_until_ms, close_t + rd.cooldown_ms)
        eq = acct.sizing_equity()
        budget = sizing.risk_budget(eq, cfg.risk.risk_pct, rd.multiplier, cfg.risk.max_risk_per_trade_inr) * size_factor
        exp_entry = plan.entry + plan.slip_in if cand.direction == "long" else plan.entry - plan.slip_in
        vol_cap = None
        if np.isfinite(F["volume"][i]):
            vol_cap = cfg.risk.max_volume_fraction * float(np.nanmedian(F["volume"][max(0, i - 48):i + 1])) / max(self.spec.contract_value, 1e-12)
        size = sizing.size_position(equity=eq, budget=budget, entry=exp_entry, stop=plan.stop, spec=self.spec,
                                    f_in=plan.f_in, f_out=plan.f_out, gst=cfg.costs.gst, slip_in=0.0,
                                    slip_out=plan.slip_out, max_leverage_used=cfg.risk.max_leverage_used,
                                    max_fraction_of_exchange_lev=cfg.risk.max_fraction_of_exchange_leverage,
                                    margin_free_fraction=cfg.risk.margin_free_fraction, risk_pct=cfg.risk.risk_pct,
                                    depth_limit_qty=vol_cap)
        gr = G.check(G.GuardInput(
            halted=acct.halted, data_fresh=fresh, daily_stop_hit=acct.daily_stop_hit(cfg.risk.daily_loss_stop_pct),
            open_positions=0, max_open_positions=cfg.risk.max_open_positions, size=size, entry=exp_entry,
            stop=plan.stop, leverage_for_liq=size.leverage if size.ok else 1.0, spec=self.spec,
            cost_r=plan.costs.cost_r + plan.funding_cost_r, rr_net=plan.costs.rr_net, max_cost_r=cfg.risk.max_cost_r,
            min_rr_net=cfg.risk.min_rr_net, in_blackout=G.in_blackout(close_t, cfg.risk.blackout_windows_utc),
            llm_verdict=llm_verdict, cooldown_active=close_t < acct.cooldown_until_ms,
            stop_to_liq_max_fraction=cfg.risk.stop_to_liq_max_fraction))
        rec.update({"planned_risk": size.planned_risk, "realised_risk": size.realised_risk, "qty": size.qty,
                    "min_equity_needed": size.min_equity_needed, "guard": gr.checks,
                    "rr_net": plan.costs.rr_net, "cost_r": plan.costs.cost_r + plan.funding_cost_r,
                    "recovery": {"multiplier": rd.multiplier, "reason": rd.reason}})
        if not gr.ok:
            rec["state"], rec["reason"] = RISK_REJECTED, gr.reason
            self._record(rec)
            return
        rec["state"] = QUALIFIED
        self._record(rec)
        trace = {k: rec[k] for k in ("score", "components", "reasons", "rr_net", "cost_r", "recovery", "regime")}
        trace["decision_id"] = uuid.uuid5(uuid.NAMESPACE_URL, f"{self.account_id}|{close_t}").hex[:12]
        trace["features"] = _snapshot(F, i)
        self.pending = PendingEntry(cand.entry_type, cand.direction, plan.entry, plan.stop, plan.target,
                                    cand.max_entry_price, size.qty, size.planned_risk, size.realised_risk,
                                    plan.f_in, plan.f_out, plan.slip_in, g + max(1, cand.expiry_bars),
                                    cand.regime, desk.score, cand.time_stop_bars, cand.breakeven_at_r,
                                    cand.strategy_id, trace)

    def _record(self, rec: dict) -> None:
        if self.record_candidates:
            self.candidates.append(rec)

    def _log_cand_update(self, pe: PendingEntry, why: str) -> None:
        if self.record_candidates and self.candidates:
            self.candidates[-1] = {**self.candidates[-1], "fill_note": why}

    # -- persistence for the paper engine ------------------------------------------
    def state_dict(self) -> dict:
        return {"pos": asdict(self.pos) if self.pos else None,
                "pending": asdict(self.pending) if self.pending else None,
                "last_i": self.last_i, "last_gap_i": self.last_gap_i, "account": self.acct.to_dict(),
                "trades_done": len(self.trades)}

    def load_state(self, d: dict) -> None:
        self.pos = Position(**d["pos"]) if d.get("pos") else None
        self.pending = PendingEntry(**d["pending"]) if d.get("pending") else None
        self.last_gap_i = d.get("last_gap_i", -10_000)
        self.last_i = d.get("last_i", -1)
        self.acct = AccountState.from_dict(d["account"])


SNAPSHOT_KEYS = ("rsi", "adx", "vol_z", "atr_pct", "bbw_rank", "vwap_dev_atr", "dist_sup_atr", "dist_res_atr",
                 "hour_ist", "weekday", "session")


def _snapshot(F: Features, i: int) -> dict:
    out = {}
    for k in SNAPSHOT_KEYS:
        v = F[k][i]
        out[k] = v.item() if hasattr(v, "item") else v
        if isinstance(out[k], float) and not np.isfinite(out[k]):
            out[k] = None
    for k in ("doji", "hammer", "bull_engulf", "bear_engulf", "shooting_star", "inside_bar", "marubozu"):
        if bool(F[k][i]):
            out.setdefault("patterns", []).append(k)
    return out


def features_to_arrays(f) -> Features:
    return {c: f[c].to_numpy() for c in f.columns}


def run(strategy: Strategy, F: Features, spec: InstrumentSpec, cfg: Config, equity0: float,
        start: int = 0, end: Optional[int] = None, **kw) -> StrategyRunner:
    acct = AccountState(starting_equity=equity0)
    r = StrategyRunner(strategy, spec, cfg, acct, **kw)
    end = len(F["close"]) if end is None else end
    for i in range(start, end):
        r.step(F, i)
    # close anything still open at the last close, marked as end-of-data
    if r.pos is not None and end > 0:
        c = float(F["close"][end - 1])
        g = int(F["open_time"][end - 1]) // TIMEFRAME_MS["5m"]
        r._close(g, c, c, "end_of_data", int(F["open_time"][end - 1]) + TIMEFRAME_MS["5m"])
    return r


_ = (json, gst_factor, DISQUALIFIED)
