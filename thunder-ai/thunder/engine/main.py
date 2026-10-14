"""The 24/7 engine process (spec 4 & 15).

Wakes shortly after each 5m candle close (demo mode: reveals the next SAMPLE DATA
bars at an accelerated pace), validates data, and for each paper sub-bot first
manages open positions then looks for new candidates — through the very same
StrategyRunner the backtester uses. All state is persisted after every batch; on
restart missed candles are replayed (stops/targets only — no new entries on old
data) and the downtime gap is logged. If state cannot be trusted it stops safely (H14).

Run:  python -m thunder.engine.main [--demo] [--once]
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import signal
import sqlite3
import threading
import time
import traceback
import uuid
from typing import Callable, Optional

from .. import strategies
from ..backtest.runner import StrategyRunner, features_to_arrays
from ..config import load_config, save_config
from ..config.loader import data_dir
from ..config.schema import Config
from ..data import downloader, store
from ..data.validators import is_stale
from ..db import backup, beat, connect, integrity_ok, kv_get, kv_set, log_event, now_ms
from ..exchanges.base import TIMEFRAME_MS, default_spec
from ..execution import paper, reconciler
from ..features import builder
from ..risk.killswitch import AccountState, ist_day
from ..secrets import ScrubFilter
from . import commands as C
from .alerts import alert
from .scheduler import feature_anchor_ms, keep_awake, next_poll_ms

log = logging.getLogger("thunder.engine")
TF = TIMEFRAME_MS["5m"]
PAPER_IDS = strategies.TRADING_IDS + ["C1"]


def setup_logging() -> None:
    d = data_dir() / "logs"
    d.mkdir(exist_ok=True)
    h = logging.handlers.RotatingFileHandler(d / "engine.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    h.addFilter(ScrubFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(x, logging.handlers.RotatingFileHandler) for x in root.handlers):
        root.addHandler(h)


class EngineStateError(RuntimeError):
    pass


class Engine:
    def __init__(self, con: sqlite3.Connection, cfg: Config, client=None, clock: Optional[Callable[[], int]] = None,
                 demo_bars_per_tick: int = 1):
        self.con, self.cfg, self.client = con, cfg, client
        self._clock = clock
        self.demo_bars_per_tick = demo_bars_per_tick
        self.runners: dict[str, StrategyRunner] = {}
        self.bg: Optional[threading.Thread] = None
        self.bg_name = ""
        self.stopped_safely = ""
        if not integrity_ok(con):
            raise EngineStateError("database failed its integrity check")
        self.load_runners()

    # -- clock & mode ---------------------------------------------------------------
    @property
    def demo(self) -> bool:
        return self.cfg.data_mode == "demo"

    def now(self) -> int:
        if self._clock:
            return self._clock()
        if self.demo:
            lt = [store.last_open_time(self.con, p, "5m") for p in self.cfg.exchange.instruments]
            lt = [x for x in lt if x]
            return (max(lt) + TF) if lt else now_ms()
        return now_ms()

    def running(self) -> bool:
        return bool(kv_get(self.con, "engine_running", False))

    # -- accounts -------------------------------------------------------------------
    def params_for(self, sid: str) -> dict:
        summ = kv_get(self.con, "arena_summary", {}) or {}
        return (summ.get(sid) or {}).get("params") or {}

    def _spec(self, pair: str):
        row = self.con.execute("SELECT spec_json FROM instruments WHERE pair=?", (pair,)).fetchone()
        if row:
            from ..exchanges.base import InstrumentSpec
            return InstrumentSpec(**json.loads(row[0]))
        return default_spec(pair, self.cfg.exchange.usdt_inr_rate)

    def load_runners(self) -> None:
        self.runners = {}
        for pair in self.cfg.exchange.instruments:
            last = store.last_open_time(self.con, pair, "5m")
            for sid in PAPER_IDS:
                acc = f"{sid}@{pair}"
                row = paper.load_account(self.con, acc)
                params = json.loads(row["params_json"]) if row else self.params_for(sid)
                strat = strategies.get(sid, **params)
                eq0 = row["starting_equity"] if row else self.cfg.capital.starting_paper_equity_inr
                r = StrategyRunner(strat, self._spec(pair), self.cfg, AccountState(starting_equity=eq0), mode="paper",
                                   account_id=acc, run_id=acc)
                if row:
                    try:
                        r.load_state(json.loads(row["state_json"]))
                    except Exception as e:  # H14: cannot establish state -> stop safely
                        raise EngineStateError(f"{acc}: saved state is unreadable ({type(e).__name__})")
                else:
                    # a new sub-bot starts trading FORWARD from the latest candle, never on history
                    r.last_i = (last // TF) if last else -1
                    paper.save_account(self.con, acc, "paper", sid, pair, strat.params, eq0, r.state_dict())
                self.runners[acc] = r

    # -- commands -------------------------------------------------------------------
    def process_commands(self) -> None:
        for row in C.pending(self.con):
            cid, cmd = row["id"], row["command"]
            args = json.loads(row["args_json"] or "{}")
            try:
                res = self._exec(cmd, args)
                C.finish(self.con, cid, True, res)
            except Exception as e:
                err = uuid.uuid4().hex[:8]
                log.error("command %s failed [%s]: %s", cmd, err, traceback.format_exc())
                C.finish(self.con, cid, False, f"Error ID {err}: {type(e).__name__}")
                log_event(self.con, "ERROR", "engine", f"Command {cmd} failed (Error ID {err}).")

    def _exec(self, cmd: str, a: dict) -> str:
        if cmd == "START":
            self.cfg = load_config()       # pick up settings saved from the dashboard
            self.persist(self.runners)
            self.load_runners()
            self.stopped_safely = ""
            kv_set(self.con, "engine_running", True); log_event(self.con, "INFO", "engine", "Engine started.")
            return "running"
        if cmd == "STOP":
            kv_set(self.con, "engine_running", False); log_event(self.con, "INFO", "engine", "Engine stopped.")
            return "stopped"
        if cmd == "SET_MODE":
            mode = a.get("data_mode")
            if mode not in ("demo", "real"):
                raise ValueError("data_mode must be demo or real")
            self.cfg = self.cfg.model_copy(update={"data_mode": mode})
            save_config(self.cfg)
            kv_set(self.con, "data_mode", mode)
            return f"data mode {mode}"
        if cmd == "RESET_PAPER":
            self.con.execute("BEGIN")
            for t in ("trades", "candidates", "equity_curve", "cash_flows"):
                self.con.execute(f"DELETE FROM {t} WHERE mode='paper'")
            self.con.execute("DELETE FROM accounts WHERE mode='paper'")
            self.con.execute("COMMIT")
            self.load_runners()
            log_event(self.con, "WARN", "engine", "Paper simulation reset by owner.")
            return "paper reset"
        if cmd == "HALT_RESET":
            ids = [a["account_id"]] if a.get("account_id") else list(self.runners)
            n = 0
            for acc in ids:
                r = self.runners[acc]
                if r.acct.halted and r.acct.human_reset(a.get("phrase", "")):
                    n += 1
                    self._save(acc)
            log_event(self.con, "WARN", "engine", f"Kill-switch reset by owner for {n} account(s).")
            return f"{n} reset"
        if cmd == "ADD_FUNDS":
            amt = float(a["amount"])
            ids = [a["account_id"]] if a.get("account_id") else list(self.runners)
            for acc in ids:
                paper.add_virtual_funds(self.con, acc, amt, self.runners[acc].acct, self.cfg.capital.deposit_shock_pct)
                self._save(acc)
            return f"{amt:+.2f} applied to {len(ids)} account(s)"
        if cmd == "CONFIRM_DEPOSIT":
            for acc, r in self.runners.items():
                r.acct.confirm_deposit(); self._save(acc)
            return "deposits confirmed"
        if cmd == "RUN_ARENA":
            return self._background("arena", self._arena_job)
        if cmd == "DOWNLOAD_DATA":
            return self._background("download", self._download_job)
        if cmd == "LOAD_DEMO":
            return self._background("demo", self._demo_job)
        if cmd == "RUN_INSIGHTS":
            from ..insights import report
            report.generate(self.con, a.get("mode", "backtest"))
            if self.con.execute("SELECT COUNT(*) FROM trades WHERE mode='paper'").fetchone()[0]:
                report.generate(self.con, "paper")
            return "insights updated"
        if cmd == "EXPORT_STRATEGY":
            from .. import cards
            summ = (kv_get(self.con, "arena_summary", {}) or {}).get(a["strategy_id"])
            if not summ:
                raise ValueError("run the arena first")
            from .evidence import status_with_paper
            summ = {**summ, "status": status_with_paper(self.con, self.cfg, a["strategy_id"], summ)}
            card = cards.build_card(a["strategy_id"], summ, self.cfg, bool((kv_get(self.con, "arena_meta", {}) or {}).get("sample_data")))
            cards.save(self.con, card)
            cards.export_dir(card, data_dir() / "cards")
            return f"card {card.card_id} saved"
        if cmd == "EXIT_ALL_HALT":
            kv_set(self.con, "live_halted", True); kv_set(self.con, "live_armed", False)
            log_event(self.con, "HALT", "live", "EXIT ALL & HALT pressed: live mode locked.")
            return "live locked"
        raise ValueError(cmd)

    def _background(self, name: str, fn) -> str:
        if self.bg and self.bg.is_alive():
            raise RuntimeError(f"{self.bg_name} is still running")
        self.bg_name = name

        def wrap():
            con = connect()
            try:
                kv_set(con, f"job_{name}", {"state": "running", "ts": now_ms(), "progress": ""})
                fn(con)
                kv_set(con, f"job_{name}", {"state": "done", "ts": now_ms()})
            except Exception:
                err = uuid.uuid4().hex[:8]
                log.error("%s job failed [%s]: %s", name, err, traceback.format_exc())
                kv_set(con, f"job_{name}", {"state": "failed", "ts": now_ms(), "error_id": err})
                log_event(con, "ERROR", name, f"{name} failed (Error ID {err}).")
            finally:
                con.close()
        self.bg = threading.Thread(target=wrap, name=name, daemon=True)
        self.bg.start()
        return f"{name} started in the background"

    def _arena_job(self, con: sqlite3.Connection) -> None:
        from ..backtest.arena import run_arena
        prog = lambda m: kv_set(con, "job_arena", {"state": "running", "ts": now_ms(), "progress": m})
        run_arena(con, self.cfg, progress=prog, lab_paths=10_000)
        from ..insights import report
        report.generate(con, "backtest")

    def _download_job(self, con: sqlite3.Connection) -> None:
        from ..exchanges.coindcx import CoinDCXPublic
        from ..exchanges.coindcx.http import Http
        cl = CoinDCXPublic(Http(self.cfg.exchange.requests_per_second), self.cfg.exchange.api_base,
                           self.cfg.exchange.public_base, self.cfg.exchange.margin_currency, self.cfg.exchange.usdt_inr_rate)
        for p in self.cfg.exchange.instruments:
            spec = cl.instrument_spec(p)
            con.execute("INSERT OR REPLACE INTO instruments(pair,spec_json,verified,fetched_at) VALUES(?,?,?,?)",
                        (p, json.dumps(spec.__dict__), 1, now_ms()))
            kv_set(con, "job_download", {"state": "running", "ts": now_ms(), "progress": p})
            downloader.download(con, cl, p, self.cfg.timeframes.history_days)

    def _demo_job(self, con: sqlite3.Connection) -> None:
        downloader.load_demo(con, self.cfg.exchange.instruments, days=180, seed=self.cfg.seed, future_days=60)

    # -- market data ----------------------------------------------------------------
    def advance_data(self) -> None:
        if self.demo:
            for p in self.cfg.exchange.instruments:
                downloader.reveal_demo(self.con, p, self.demo_bars_per_tick)
        else:
            if self.client is None:
                from ..exchanges.coindcx import CoinDCXPublic
                from ..exchanges.coindcx.http import Http
                self.client = CoinDCXPublic(Http(self.cfg.exchange.requests_per_second), self.cfg.exchange.api_base,
                                            self.cfg.exchange.public_base, self.cfg.exchange.margin_currency,
                                            self.cfg.exchange.usdt_inr_rate)
            for p in self.cfg.exchange.instruments:
                try:
                    downloader.download(self.con, self.client, p, 2, now=self.now())
                    beat(self.con, f"fetch:{p}", "ok")
                except Exception as e:
                    log_event(self.con, "WARN", "data", f"{p}: fetch failed ({type(e).__name__}); will retry.")

    # -- the bar loop ---------------------------------------------------------------
    def process_pair(self, pair: str) -> int:
        rs = {k: r for k, r in self.runners.items() if k.endswith("@" + pair)}
        if not rs:
            return 0
        last_g = min(r.last_i for r in rs.values())
        new = store.load_candles(self.con, pair, "5m", start_ms=(last_g + 1) * TF if last_g >= 0 else None)
        if new.empty:
            return 0
        now = self.now()
        if last_g >= 0 and int(new["open_time"].iloc[0]) // TF - last_g > 1:
            log_event(self.con, "WARN", "engine", f"{pair}: downtime gap of {int(new['open_time'].iloc[0]) // TF - last_g - 1} "
                      "candles; replaying them for stops/targets only.")
        anchors = new["open_time"].map(feature_anchor_ms)
        done = 0
        for anchor in sorted(anchors.unique()):
            grp = new[anchors == anchor]
            last_ot = int(grp["open_time"].iloc[-1])
            win = store.load_candles(self.con, pair, "5m", start_ms=int(anchor), end_ms=last_ot + TF)
            f = builder.build(win)
            F = features_to_arrays(f)
            first = int(grp["open_time"].iloc[0])
            idx = [i for i, t in enumerate(F["open_time"]) if t >= first]
            for i in idx:
                bar_close = int(F["open_time"][i]) + TF
                fresh = not is_stale(int(F["open_time"][i]), "5m", now, self.cfg.risk.stale_multiple) and bar_close <= now
                for acc, r in rs.items():
                    was_halted = r.acct.halted
                    r.step(F, i, data_fresh=fresh)
                    if r.acct.halted and not was_halted:
                        alert(self.con, self.cfg, "HALT", "risk", f"{acc}: kill-switch — {r.acct.halt_reason}. "
                              "Needs a human reset on the Risk page.")
                done += 1
            self.persist(rs)
            j = len(F["close"]) - 1
            mn = kv_get(self.con, "market_now", {}) or {}
            mn[pair] = {"regime": str(F["regime"][j]), "close": float(F["close"][j]), "ts": int(F["open_time"][j]) + TF,
                        "atr_pct": float(F["atr_pct"][j]) if F["atr_pct"][j] == F["atr_pct"][j] else None}
            kv_set(self.con, "market_now", mn)
        return done

    def persist(self, rs: dict[str, StrategyRunner]) -> None:
        from ..backtest.arena import insert_trade
        self.con.execute("BEGIN")
        try:
            for acc, r in rs.items():
                for t in r.trades:
                    insert_trade(self.con, t, acc, self.demo)
                for c in r.candidates:
                    self.con.execute("INSERT OR IGNORE INTO candidates(mode,run_id,account_id,strategy_id,instrument,candle_close_time,"
                                     "direction,state,reason,score,components_json,reports_json,llm_json,regime) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                     ("paper", acc, acc, c["strategy_id"], c["instrument"], c["candle_close_time"], c["direction"],
                                      c["state"], c["reason"], c["score"], json.dumps(c["components"]),
                                      json.dumps({"reports": c["reports"], "challenge": c["challenge"], "reasons": c["reasons"],
                                                  "guard": c.get("guard"), "rr_net": c.get("rr_net"), "cost_r": c.get("cost_r"),
                                                  "min_equity_needed": c.get("min_equity_needed")}, default=str),
                                      json.dumps(c.get("llm")) if c.get("llm") else None, c["regime"]))
                for k, (ts, eq) in enumerate(r.equity_curve):
                    if k == len(r.equity_curve) - 1 or (ts // TF) % 3 == 0:
                        self.con.execute("INSERT OR REPLACE INTO equity_curve(mode,account_id,ts,equity,peak,net_cash_flows) VALUES(?,?,?,?,?,?)",
                                         ("paper", acc, ts, eq, r.acct.peak, r.acct.net_cash_flows))
                r.trades, r.candidates, r.equity_curve = [], [], []
                paper.save_account(self.con, acc, "paper", r.s.id, r.spec.pair, r.s.params, r.acct.starting_equity, r.state_dict())
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def _save(self, acc: str) -> None:
        r = self.runners[acc]
        paper.save_account(self.con, acc, "paper", r.s.id, r.spec.pair, r.s.params, r.acct.starting_equity, r.state_dict())

    # -- one cycle --------------------------------------------------------------------
    def tick(self) -> dict:
        self.process_commands()
        info = {"running": self.running(), "bars": 0}
        if self.running() and not self.stopped_safely:
            self.advance_data()
            for p in self.cfg.exchange.instruments:
                info["bars"] += self.process_pair(p)
            self._live()
            problems = reconciler.check_paper(self.con, self.runners)
            if problems:
                self.stopped_safely = "; ".join(problems)
                kv_set(self.con, "engine_running", False)
                alert(self.con, self.cfg, "HALT", "reconciler", "Stopped safely: " + self.stopped_safely)
            self._daily()
        last = {p: store.last_open_time(self.con, p, "5m") for p in self.cfg.exchange.instruments}
        beat(self.con, "engine", json.dumps({"running": self.running(), "mode": self.cfg.data_mode, "last": last,
                                            "now": self.now(), "stopped_safely": self.stopped_safely,
                                            "bg": self.bg_name if self.bg and self.bg.is_alive() else ""}))
        self._uptime()
        return info

    def _live(self) -> None:
        """Drive the live bridge only when the owner has armed live mode (all Section 17 gates)."""
        if not kv_get(self.con, "live_armed", False):
            self.bridge = None
            return
        from .. import cards
        from ..exchanges.coindcx import CoinDCXPrivate
        from ..secrets import get_secret
        from .live_bridge import LiveBridge
        if getattr(self, "bridge", None) is None:
            cid = kv_get(self.con, "live_card_id", None)
            card = next((c for c in cards.load_all(self.con) if c.card_id == cid), None)
            key, sec = get_secret("coindcx_api_key"), get_secret("coindcx_api_secret")
            if card is None or not key or not sec:
                return
            shadow = self.runners.get(f"{card.strategy_id}@{card.instruments[0]}")
            if shadow is None:
                return
            self.bridge = LiveBridge(self.con, self.cfg, card, CoinDCXPrivate(key, sec, api_base=self.cfg.exchange.api_base,
                                     margin_currency=self.cfg.exchange.margin_currency), shadow)
        self.bridge.after_step()
        self.bridge.reconcile()

    def _uptime(self) -> None:
        hour = now_ms() // 3_600_000
        u = kv_get(self.con, "uptime_hours", []) or []
        if not u or u[-1] != hour:
            u = (u + [hour])[-24 * 90:]
            kv_set(self.con, "uptime_hours", u)

    def _daily(self) -> None:
        d = ist_day(now_ms())
        if kv_get(self.con, "last_daily", None) != d:
            kv_set(self.con, "last_daily", d)
            try:
                backup()
                from ..insights import report
                if self.con.execute("SELECT COUNT(*) FROM trades WHERE mode='paper'").fetchone()[0]:
                    report.generate(self.con, "paper")
            except Exception as e:
                log_event(self.con, "WARN", "engine", f"daily housekeeping: {type(e).__name__}")

    def run_forever(self, demo_interval_s: float = 2.0) -> None:
        keep_awake()
        stop = {"flag": False}
        signal.signal(signal.SIGTERM, lambda *a: stop.update(flag=True))
        try:
            signal.signal(signal.SIGINT, lambda *a: stop.update(flag=True))
        except ValueError:
            pass
        log_event(self.con, "INFO", "engine", "Engine process online.")
        while not stop["flag"]:
            t0 = time.time()
            try:
                self.tick()
            except EngineStateError as e:
                alert(self.con, self.cfg, "HALT", "engine", f"Stopped safely: {e}")
                kv_set(self.con, "engine_running", False)
            except Exception:
                err = uuid.uuid4().hex[:8]
                log.error("tick failed [%s]: %s", err, traceback.format_exc())
                log_event(self.con, "ERROR", "engine", f"Cycle failed (Error ID {err}); retrying.")
            if self.demo:
                wait = demo_interval_s
            else:
                wait = max(1.0, min(5.0, (next_poll_ms(now_ms()) - now_ms()) / 1000))
            # commands are checked every second so the dashboard feels responsive
            end = t0 + wait
            while time.time() < end and not stop["flag"]:
                time.sleep(0.5)
                if C.pending(self.con):
                    break
        (data_dir() / "engine.pid").unlink(missing_ok=True)
        log_event(self.con, "INFO", "engine", "Engine process stopped.")


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use bundled SAMPLE DATA")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--speed", type=float, default=2.0, help="demo: seconds per revealed candle")
    a = ap.parse_args(argv)
    setup_logging()
    cfg = load_config()
    if a.demo and cfg.data_mode != "demo":
        cfg = cfg.model_copy(update={"data_mode": "demo"})
    con = connect()
    (data_dir() / "engine.pid").write_text(str(__import__("os").getpid()))
    if cfg.data_mode == "demo" and not store.last_open_time(con, cfg.exchange.instruments[0], "5m"):
        downloader.load_demo(con, cfg.exchange.instruments, days=180, seed=cfg.seed, future_days=60)
    try:
        eng = Engine(con, cfg)
    except EngineStateError as e:
        log_event(con, "HALT", "engine", f"Engine refused to start: {e}")
        raise SystemExit(2)
    if a.once:
        print(eng.tick())
        return
    eng.run_forever(a.speed)


if __name__ == "__main__":
    main()
