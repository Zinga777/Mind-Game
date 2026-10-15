"""Known-answer money maths (spec 10, 11.2, 12, 21)."""
import math

import pytest

from tests.conftest import unit_spec
from thunder.risk.recovery import martingale_ruin_table
from thunder.trade import costs, sizing


def test_sizing_known_answer_taker_both_sides():
    den = sizing.per_unit_loss(100, 99.5, 0.0005, 0.0005, 0.18)
    assert den == pytest.approx(0.617705, abs=1e-9)
    r = sizing.size_position(equity=3000, budget=15, entry=100, stop=99.5, spec=unit_spec(qty_step=0.0001, min_qty=0.0001),
                             f_in=0.0005, f_out=0.0005, gst=0.18)
    assert r.q_raw == pytest.approx(24.2834, abs=1e-4)
    assert r.q_raw * 100 == pytest.approx(2428.34, abs=0.01)
    naive = 15 / 0.5
    assert naive == 30 and naive * den > 15  # naive formula under-states the loss


def test_sizing_known_answer_maker_in_taker_out():
    r = sizing.size_position(equity=3000, budget=15, entry=100, stop=99.5, spec=unit_spec(qty_step=0.0001, min_qty=0.0001),
                             f_in=0.0002, f_out=0.0005, gst=0.18)
    assert r.q_raw == pytest.approx(25.7597, abs=1e-4)


def test_fee_examples():
    assert costs.round_trip_fee(3000, 0.0002, 0.0002, 0.18) == pytest.approx(1.416, abs=1e-6)
    assert costs.round_trip_fee(3000, 0.0005, 0.0005, 0.18) == pytest.approx(3.54, abs=1e-6)


def test_rr_gross_long_and_short():
    assert costs.rr_gross(100, 99.5, 101, "long") == pytest.approx(2.0)
    assert costs.rr_gross(100, 100.5, 99, "short") == pytest.approx(2.0)


def test_breakeven_table():
    assert costs.breakeven_winrate(1.5, 0.10) == pytest.approx(0.44)
    assert costs.breakeven_winrate(1.5, 0.25) == pytest.approx(0.50)
    assert costs.breakeven_winrate(1.5, 0.40) == pytest.approx(0.56)
    assert costs.breakeven_winrate(1.0, 0.25) == pytest.approx(0.625)


def test_trade_costs_components():
    tc = costs.trade_costs(100, 99.5, 101, "long", 0.0005, 0.0005, 0.18)
    assert tc.loss_per_unit == pytest.approx(0.617705)
    assert tc.gain_per_unit == pytest.approx(1 - 1.18 * 0.05 - 1.18 * 101 * 0.0005)
    assert tc.cost_r == pytest.approx((0.059 + 0.0587050) / 0.5)


def test_rounding_never_rounds_up():
    assert sizing.floor_to_step(24.99999, 1) == 24
    assert sizing.floor_to_step(0.0299, 0.01) == pytest.approx(0.02)
    r = sizing.size_position(equity=3000, budget=15, entry=100, stop=99.5, spec=unit_spec(qty_step=1, min_qty=1),
                             f_in=0.0005, f_out=0.0005, gst=0.18)
    assert r.ok and r.qty == 24 and r.realised_risk <= 15


def test_reject_when_min_order_exceeds_budget():
    r = sizing.size_position(equity=3000, budget=15, entry=100, stop=99.5, spec=unit_spec(min_qty=30, qty_step=1),
                             f_in=0.0005, f_out=0.0005, gst=0.18, risk_pct=0.005)
    assert not r.ok and r.reason.startswith("UNDERCAPITALISED")
    # min_equity_needed = risk of min order / risk_pct
    assert r.min_equity_needed == pytest.approx(30 * 0.617705 / 0.005)


def test_dynamic_capital_scales_budget():
    assert sizing.risk_budget(3000, 0.005) == pytest.approx(15)
    assert sizing.risk_budget(30000, 0.005) == pytest.approx(150)
    # recovery multiplier can never push per-trade risk above 1% of equity
    assert sizing.risk_budget(3000, 0.005, 5.0) == pytest.approx(30)
    assert sizing.risk_budget(3000, 0.005, 1.0, max_risk_inr=10) == 10
    assert sizing.tradable_equity(5000, 3000) == 3000


def test_impact_guard_caps_quantity():
    r = sizing.size_position(equity=100000, budget=500, entry=100, stop=99, spec=unit_spec(),
                             f_in=0.0005, f_out=0.0005, gst=0.18, depth_limit_qty=10)
    assert r.ok and r.qty == 10


def test_leverage_and_margin_rejections():
    r = sizing.size_position(equity=1000, budget=5, entry=100, stop=99.99, spec=unit_spec(),
                             f_in=0.0, f_out=0.0, gst=0.18, max_leverage_used=5)
    assert not r.ok and "exceeds cap" in r.reason


def test_liquidation_distance():
    assert sizing.liquidation_distance(5, 0.005) == pytest.approx(0.195)
    assert sizing.liquidation_distance(10, 0.005) == pytest.approx(0.095)
    assert sizing.stop_within_liq_limit(100, 91, 5, 0.005) is True    # 9% < 9.75%
    assert sizing.stop_within_liq_limit(100, 89, 5, 0.005) is False


def test_martingale_ruin_arithmetic():
    rows = martingale_ruin_table(15, 3000)
    r7 = rows[6]
    assert r7["cumulative_loss"] == pytest.approx(1905)
    assert r7["next_risk"] == pytest.approx(1920)
    assert r7["left"] == pytest.approx(1095)
    assert r7["can_continue"] is False
    assert 0.5 ** 7 == pytest.approx(0.0078125)
    assert math.isclose(15 * (2 ** 7 - 1), 1905)
