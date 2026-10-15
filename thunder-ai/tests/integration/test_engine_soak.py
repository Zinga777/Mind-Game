"""Soak / restart test (spec 15): replay months of data through the real-time engine path, kill and
restart the engine at random points, and require results identical to an uninterrupted run."""
import random

import pytest

from thunder.config import Config
from thunder.data.downloader import load_demo
from thunder.db import connect, kv_set
from thunder.engine import commands as C
from thunder.engine.main import Engine


def _cfg():
    c = Config()
    c.capital.starting_paper_equity_inr = 100_000.0   # big enough that trades are feasible and get compared
    return c


def _replay(db, restarts: set[int], ticks: int, bars_per_tick: int):
    cfg = _cfg()
    con = connect(db)
    load_demo(con, cfg.exchange.instruments, days=50, seed=5, future_days=90)
    kv_set(con, "engine_running", True)
    eng = Engine(con, cfg, demo_bars_per_tick=bars_per_tick)
    for t in range(ticks):
        if t in restarts:                       # simulated kill -9: drop everything in memory
            con.close()
            con = connect(db)
            eng = Engine(con, cfg, demo_bars_per_tick=bars_per_tick)
        eng.tick()
    rows = con.execute("SELECT account_id, entry_time, exit_time, side, round(net_pnl, 6) FROM trades WHERE mode='paper' "
                       "ORDER BY account_id, entry_time").fetchall()
    eq = con.execute("SELECT account_id, state_json FROM accounts ORDER BY account_id").fetchall()
    con.close()
    return [tuple(r) for r in rows], [(a, s) for a, s in eq]


@pytest.mark.slow
def test_soak_restart_identical(tmp_path):
    ticks, bpt = 40, 648            # 40 x 648 bars = 90 days of 5m candles per instrument
    rng = random.Random(42)
    restarts = set(rng.sample(range(1, ticks), 6))
    a_trades, a_state = _replay(tmp_path / "a.db", set(), ticks, bpt)
    b_trades, b_state = _replay(tmp_path / "b.db", restarts, ticks, bpt)
    assert len(a_trades) > 20
    assert a_trades == b_trades
    assert a_state == b_state


def test_commands_roundtrip(tmp_path):
    cfg = _cfg()
    con = connect(tmp_path / "c.db")
    load_demo(con, cfg.exchange.instruments, days=50, seed=5, future_days=3)
    eng = Engine(con, cfg, demo_bars_per_tick=50)
    cid = C.submit(con, "START")
    eng.tick()
    assert C.status(con, cid)["status"] == "done" and eng.running()
    C.submit(con, "ADD_FUNDS", amount=500.0)
    eng.tick()
    acc = next(iter(eng.runners.values())).acct
    assert acc.net_cash_flows == 500.0
    bad = C.submit(con, "HALT_RESET", phrase="nope")
    eng.tick()
    assert C.status(con, bad)["status"] == "done"
    with pytest.raises(ValueError):
        C.submit(con, "DROP_TABLES")
    C.submit(con, "STOP")
    eng.tick()
    assert not eng.running()
    con.close()


def test_corrupt_state_stops_safely(tmp_path):
    from thunder.engine.main import EngineStateError
    cfg = _cfg()
    con = connect(tmp_path / "d.db")
    load_demo(con, cfg.exchange.instruments, days=50, seed=5, future_days=1)
    Engine(con, cfg)
    con.execute("UPDATE accounts SET state_json='{not json' WHERE account_id='S1@B-BTC_USDT'")
    with pytest.raises(EngineStateError):
        Engine(con, cfg)
    con.close()


def test_switch_to_real_purges_sample_data(tmp_path):
    cfg = _cfg()
    con = connect(tmp_path / "e.db")
    load_demo(con, cfg.exchange.instruments, days=50, seed=5, future_days=3)
    kv_set(con, "engine_running", True)
    eng = Engine(con, cfg, demo_bars_per_tick=500)
    eng.tick()
    eng._exec("SET_MODE", {"data_mode": "real"})
    assert con.execute("SELECT COUNT(*) FROM candles WHERE source='synthetic'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM trades WHERE mode='paper'").fetchone()[0] == 0
    eng._exec("SET_MODE", {"data_mode": "demo"})
    con.close()
