"""Bar-by-bar engine: fills, ordering, costs, funding, guards, determinism, restart idempotency."""
import copy

import numpy as np
import pytest

from tests.conftest import OneShot, make_df, unit_spec
from thunder import strategies
from thunder.backtest.runner import StrategyRunner, features_to_arrays, run
from thunder.execution.fills import bar_exit, limit_filled
from thunder.features import builder
from thunder.risk.killswitch import AccountState

AT = 500


def frame(edit=None, n=700, seed=1):
    df = make_df(n, seed=seed)
    if edit:
        edit(df)
    return features_to_arrays(builder.build(df)), df


def cfg0(cfg, **risk):
    c = cfg.model_copy(deep=True)
    c.council.threshold = 0
    for k, v in risk.items():
        setattr(c.risk, k, v)
    return c


def test_bar_exit_stop_first_and_gap():
    assert bar_exit("long", 99, 103, 100, 104, 98, 0.0, 0.0) == ("stop", 99)
    assert bar_exit("long", 99, 103, 97, 104, 96, 0.1, 0.0) == ("stop_gap", 96.9)
    assert bar_exit("short", 101, 97, 100, 102, 96, 0.0, 0.0) == ("stop", 101)
    assert bar_exit("long", 99, 103, 100, 103.5, 99.5, 0.0, 0.2) == ("target", 102.8)


def test_limit_fill_needs_trade_through_by_one_tick():
    assert not limit_filled("long", 100.0, 100.0, 101, 0.01)
    assert limit_filled("long", 100.0, 99.99, 101, 0.01)
    assert limit_filled("short", 100.0, 99, 100.01, 0.01)


def _set_bar(df, i, o, h, l, c):
    df.loc[i, ["open", "high", "low", "close"]] = [o, h, l, c]


def test_intrabar_both_touched_assumes_stop(cfg):
    def ed(df):
        c = df.loc[AT, "close"]
        _set_bar(df, AT + 1, c, c * 1.001, c * 0.999, c)
        _set_bar(df, AT + 2, c, c * 1.05, c * 0.95, c)  # touches target AND stop
    F, _ = frame(ed)
    r = run(OneShot(AT), F, unit_spec(), cfg0(cfg), 100_000, 0, AT + 3)
    assert len(r.trades) == 1 and r.trades[0]["exit_reason"] == "stop"


def test_gap_through_stop_fills_at_worse_open(cfg):
    def ed(df):
        c = df.loc[AT, "close"]
        _set_bar(df, AT + 1, c, c * 1.001, c * 0.999, c)
        _set_bar(df, AT + 2, c * 0.95, c * 0.96, c * 0.94, c * 0.95)
    F, df = frame(ed)
    r = run(OneShot(AT), F, unit_spec(), cfg0(cfg), 100_000, 0, AT + 3)
    t = r.trades[0]
    assert t["exit_reason"] == "stop_gap"
    assert t["exit"] < df.loc[AT, "close"] * 0.99 * 0.99  # far worse than the stop level


def test_cost_breakdown_sums_to_net_and_matches_prices(cfg):
    class Many(OneShot):
        def detect(self, F, i):
            self.at, self.dir = i, ("long" if i % 2 else "short")
            return super().detect(F, i) if i >= 400 else None
    F, _ = frame(n=1500)
    F["funding_rate"] = np.full(len(F["close"]), 0.0002)
    r = run(Many(0, time_stop=30), F, unit_spec(), cfg0(cfg), 100_000, 0, 1500)
    assert len(r.trades) >= 5
    for t in r.trades:
        parts = t["gross_pnl"] - t["fee_entry"] - t["fee_exit"] - t["gst"] - t["slippage"] - t["funding"]
        assert parts == pytest.approx(t["net_pnl"], abs=1e-9)
        sgn = 1 if t["side"] == "long" else -1
        direct = (t["exit"] - t["entry"]) * sgn * t["qty"] - (t["fee_entry"] + t["fee_exit"]) * 1.18 - t["funding"]
        assert direct == pytest.approx(t["net_pnl"], abs=1e-6)
        assert t["gst"] == pytest.approx(0.18 * (t["fee_entry"] + t["fee_exit"]))
        assert t["realised_risk"] <= t["planned_risk"] + 1e-9


@pytest.mark.parametrize("side,sign", [("long", 1), ("short", -1)])
def test_funding_sign(cfg, side, sign):
    def ed(df):
        c = df.loc[AT, "close"]
        for k in range(AT + 1, AT + 120):  # flat: no exit, so the position crosses a funding time
            _set_bar(df, k, c, c * 1.0005, c * 0.9995, c)
    F, _ = frame(ed)
    F["funding_rate"] = np.full(len(F["close"]), 0.001)
    r = run(OneShot(AT, direction=side, time_stop=110), F, unit_spec(), cfg0(cfg), 100_000, 0, AT + 120)
    t = r.trades[0]
    assert t["exit_reason"] == "time_stop"
    assert np.sign(t["funding"]) == sign  # positive rate: longs pay (cost > 0), shorts receive


def test_limit_entry_not_filled_without_trade_through(cfg):
    def ed(df):
        c = df.loc[AT, "close"]
        _set_bar(df, AT + 1, c * 1.001, c * 1.002, c, c * 1.001)       # touches but not through
        _set_bar(df, AT + 2, c * 1.001, c * 1.002, c * 1.0005, c * 1.001)
        for k in range(AT + 3, AT + 10):
            _set_bar(df, k, c * 1.002, c * 1.003, c * 1.001, c * 1.002)
    F, _ = frame(ed)
    r = run(OneShot(AT, entry_type="limit"), F, unit_spec(), cfg0(cfg), 100_000, 0, AT + 10)
    assert not r.trades and r.pos is None and r.pending is None


def test_no_trade_without_valid_stop(cfg):
    class BadStop(OneShot):
        def detect(self, F, i):
            c = super().detect(F, i)
            if c:
                c.stop = c.ref_price * 1.01  # long with stop ABOVE entry
            return c
    F, _ = frame()
    r = run(BadStop(AT), F, unit_spec(), cfg0(cfg), 100_000, 0, 700)
    assert not r.trades
    assert r.candidates[0]["state"] == "DISQUALIFIED" and "stop" in r.candidates[0]["reason"]


def test_only_one_position_at_a_time(cfg):
    class Every(OneShot):
        def detect(self, F, i):
            self.at = i
            return super().detect(F, i) if i >= 400 else None
    F, _ = frame()
    r = run(Every(0), F, unit_spec(), cfg0(cfg), 100_000, 0, 700)
    assert len(r.trades) >= 2
    for a, b in zip(r.trades, r.trades[1:]):
        assert b["entry_time"] >= a["exit_time"] - 300_000


def test_stale_data_blocks_entries(cfg):
    F, _ = frame()
    r = StrategyRunner(OneShot(AT), unit_spec(), cfg0(cfg), AccountState(starting_equity=100_000))
    for i in range(0, AT + 1):
        r.step(F, i, data_fresh=(i != AT))
    assert r.pending is None and r.candidates[0]["reason"] == "stale or inconsistent data"


def test_daily_loss_stop_blocks_entries(cfg):
    F, _ = frame()
    acct = AccountState(starting_equity=100_000)
    r = StrategyRunner(OneShot(AT), unit_spec(), cfg0(cfg), acct)
    for i in range(0, AT):
        r.step(F, i)
    acct.day_realised = -0.03 * acct.day_start_equity
    r.step(F, AT)
    assert r.pending is None and r.candidates[0]["state"] == "RISK_REJECTED" and "daily loss" in r.candidates[0]["reason"]


def test_killswitch_blocks_entries_until_human_reset(cfg):
    F, _ = frame()
    acct = AccountState(starting_equity=100_000)
    acct.halted = True
    r = StrategyRunner(OneShot(AT), unit_spec(), cfg0(cfg), acct)
    for i in range(0, AT + 1):
        r.step(F, i)
    assert r.candidates[0]["reason"].startswith("kill-switch")


def test_deterministic_reruns(cfg):
    df = make_df(3000, seed=9)
    F = features_to_arrays(builder.build(df))
    for sid in ("S1", "S4", "C1"):
        a = run(strategies.get(sid), F, unit_spec(), cfg, 100_000)
        b = run(strategies.get(sid), F, unit_spec(), cfg, 100_000)
        assert [t["net_pnl"] for t in a.trades] == [t["net_pnl"] for t in b.trades]
        assert len(a.candidates) == len(b.candidates)


def test_restart_mid_run_is_idempotent(cfg):
    df = make_df(3000, seed=11)
    F = features_to_arrays(builder.build(df))
    full = run(strategies.get("C1", prob=1 / 40), F, unit_spec(), cfg, 100_000)
    assert len(full.trades) > 5
    r1 = StrategyRunner(strategies.get("C1", prob=1 / 40), unit_spec(), cfg, AccountState(starting_equity=100_000))
    trades = []
    cut = 1700
    for i in range(cut):
        r1.step(F, i)
    trades += r1.trades
    state = copy.deepcopy(r1.state_dict())
    r2 = StrategyRunner(strategies.get("C1", prob=1 / 40), unit_spec(), cfg, AccountState(starting_equity=1))
    r2.load_state(state)
    for i in range(cut - 50, 3000):     # replaying already-processed bars must be a no-op
        r2.step(F, i)
    if r2.pos is not None:
        c = float(F["close"][-1])
        r2._close(int(F["open_time"][-1]) // 300_000, c, c, "end_of_data", int(F["open_time"][-1]) + 300_000)
    trades += r2.trades
    assert [round(t["net_pnl"], 9) for t in trades] == [round(t["net_pnl"], 9) for t in full.trades]
