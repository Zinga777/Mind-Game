"""Cash flows are never profit/loss; drawdown and kill-switch are cash-flow adjusted (spec 11.7)."""
import re
from pathlib import Path

import pytest

from thunder.risk.killswitch import HALT_CONFIRM_PHRASE, AccountState

T = 1_735_689_600_000


def test_pnl_and_twr_with_deposit_and_withdrawal():
    a = AccountState(starting_equity=3000)
    a.apply_trade(300, 1.0, "RANGE", T)            # +10%
    a.apply_cash_flow(3300, T + 1)                 # deposit doubles equity
    a.apply_trade(660, 1.0, "RANGE", T + 2)        # +10% on 6600
    a.apply_cash_flow(-2000, T + 3)                # withdrawal
    assert a.net_pnl() == pytest.approx(300 + 660)
    assert a.equity == pytest.approx(3000 + 300 + 3300 + 660 - 2000)
    assert a.time_weighted_return() == pytest.approx(1.1 * 1.1 - 1)


def test_deposit_does_not_hide_drawdown():
    a = AccountState(starting_equity=3000)
    a.apply_trade(-240, -1, "RANGE", T)            # 8% drawdown
    a.apply_cash_flow(3000, T + 1)
    assert a.drawdown() == pytest.approx(240 / 6000)  # the deposit raised the peak too: still 4% down
    assert a.peak == pytest.approx(6000)
    a.mark(a.equity, 0.10)
    assert not a.halted
    a.apply_trade(-400, -1, "RANGE", T + 2)
    a.mark(a.equity, 0.10)
    assert a.halted                                 # 640 below a 6000 peak = 10.7%


def test_withdrawal_does_not_trip_killswitch():
    a = AccountState(starting_equity=3000)
    a.apply_cash_flow(-1000, T)
    a.mark(a.equity, 0.10)
    assert not a.halted and a.drawdown() == pytest.approx(0)


def test_deposit_shock_guard_until_confirmed():
    a = AccountState(starting_equity=3000)
    a.apply_cash_flow(3000, T, deposit_shock_pct=0.25, confirmed=False)
    assert a.sizing_equity() == 3000
    a.confirm_deposit()
    assert a.sizing_equity() == 6000
    b = AccountState(starting_equity=3000)
    b.apply_cash_flow(500, T, confirmed=False)       # below 25%: applies immediately
    assert b.sizing_equity() == 3500


def test_daily_loss_stop_uses_start_of_day_equity():
    a = AccountState(starting_equity=3000)
    a.roll_day(T)
    a.apply_trade(-59, -1, "RANGE", T + 1)
    assert not a.daily_stop_hit(0.02)
    a.apply_trade(-1, -1, "RANGE", T + 2)
    assert a.daily_stop_hit(0.02)
    a.roll_day(T + 86_400_000)
    assert not a.daily_stop_hit(0.02)


def test_killswitch_needs_typed_human_reset():
    a = AccountState(starting_equity=1000)
    a.apply_trade(-150, -1, "RANGE", T)
    a.mark(a.equity, 0.10)
    assert a.halted
    assert not a.human_reset("yes")
    assert a.halted
    assert a.human_reset(HALT_CONFIRM_PHRASE)
    assert not a.halted


def test_no_hard_coded_3000_in_code_paths():
    root = Path(__file__).resolve().parents[2] / "thunder"
    bad = []
    for p in root.rglob("*.py"):
        if p.name == "schema.py":           # the documented, editable defaults live here only
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if re.search(r"(?<![\d.])3_?000(\.0)?(?![\d_])", code):
                bad.append(f"{p.relative_to(root)}:{n}: {line.strip()}")
    assert not bad, "hard-coded 3000 found:\n" + "\n".join(bad)
