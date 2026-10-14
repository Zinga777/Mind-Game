"""Statistical tooling: bootstrap reproducibility, permutation-test calibration, BH, promotion ladder, Recovery Lab."""
import numpy as np
import pytest

from thunder.backtest import metrics, promotion
from thunder.config.schema import GatesCfg
from thunder.risk.recovery_lab import run_lab, simulate_path


def test_bootstrap_ci_reproducible():
    x = np.random.default_rng(1).normal(0.1, 1, 200)
    assert metrics.bootstrap_ci(x, seed=5) == metrics.bootstrap_ci(x, seed=5)
    lo, hi = metrics.bootstrap_ci(x)
    assert lo < x.mean() < hi


def test_permutation_test_false_positive_rate_close_to_alpha():
    rng = np.random.default_rng(0)
    trials, hits = 200, 0
    for k in range(trials):
        a, b = rng.normal(0, 1, 60), rng.normal(0, 1, 200)
        if metrics.permutation_pvalue(a, b, n=400, seed=k) < 0.05:
            hits += 1
    assert 0.01 <= hits / trials <= 0.10   # calibrated on a known-null strategy


def test_permutation_detects_real_edge():
    rng = np.random.default_rng(1)
    assert metrics.permutation_pvalue(rng.normal(0.5, 1, 150), rng.normal(0, 1, 300), n=2000) < 0.01


def test_benjamini_hochberg():
    q = metrics.benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert q["a"] == pytest.approx(0.04) and q["c"] == pytest.approx(0.0533, abs=1e-3) and q["d"] == 0.5
    assert all(q[k] >= v for k, v in {"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5}.items())


def _ev(**kw):
    base = dict(oos_trades=150, oos_expectancy_r=0.25, oos_pf=1.5, oos_max_dd=0.06, q_value=0.01, ci_low=0.05,
                exp_cost15=0.1, exp_minus_best3=0.15, neighbour_share=0.8, max_month_share=0.25, both_instruments=True)
    base.update(kw)
    return base


def test_promotion_known_edge_passes_no_edge_fails_overfit_flagged():
    g = GatesCfg()
    assert promotion.evaluate(_ev(), g).status == promotion.CONFIRMED
    assert promotion.evaluate(_ev(oos_expectancy_r=-0.02, oos_pf=0.95, q_value=0.6), g).status == promotion.RESEARCH
    # over-fit: great on OOS sample but fragile neighbours / costs -> stops at CANDIDATE
    v = promotion.evaluate(_ev(neighbour_share=0.2, exp_cost15=-0.05), g)
    assert v.status == promotion.CANDIDATE
    assert promotion.evaluate(_ev(oos_trades=60), g).status == promotion.RESEARCH
    assert promotion.evaluate(_ev(oos_trades=60), g).tentative
    paper = dict(paper_days=35, paper_trades=60, paper_expectancy=0.2, slippage_within=True, uptime=0.97, recon_errors=0)
    assert promotion.evaluate(_ev(**paper), g).status == promotion.PAPER_PROVEN
    assert promotion.evaluate(_ev(**paper, owner_action=True), g).status == promotion.LIVE_ELIGIBLE
    assert promotion.evaluate(_ev(**{**paper, "paper_days": 10}), g).status == promotion.CONFIRMED


def test_recovery_lab_policy_rules_and_ruin_demo():
    rng = np.random.default_rng(3)
    r = rng.choice([-1.0, 1.4], size=300, p=[0.55, 0.45])
    lab = run_lab(r, 3000.0 * 1, n_paths=500, seed=1)
    assert set(lab.table) == {"A", "B", "C", "D"}
    a, b = lab.table["A"], lab.table["B"]
    expect_b = b["median_end"] > a["median_end"] and b["p5_end"] > a["p5_end"] and b["p_kill"] <= a["p_kill"] + 0.02
    assert lab.b_allowed == expect_b
    assert lab.table["D"]["p_ruin"] >= lab.table["A"]["p_ruin"]  # Martingale is the worst on ruin
    # deterministic Martingale ruin path: 7 straight losses from 0.5% risk on 3000
    out = simulate_path(np.array([-1.0] * 8), "D", 3000.0, 0.005)
    assert out["ruined"]
    assert run_lab(np.array([0.1] * 5), 1000.0).b_allowed is False  # too few trades -> A


def test_metrics_basic():
    trades = [{"r_multiple": 1.0, "net_pnl": 10, "gross_pnl": 12, "realised_risk": 10, "exit_time": 1, "bars_held": 3, "mae_r": .2, "mfe_r": 1},
              {"r_multiple": -1.0, "net_pnl": -10, "gross_pnl": -8, "realised_risk": 10, "exit_time": 2, "bars_held": 2, "mae_r": 1, "mfe_r": .1}]
    m = metrics.compute(trades, [(0, 100.0), (1, 110.0), (2, 100.0)], 100.0)
    assert m["trades"] == 2 and m["expectancy_r"] == 0 and m["profit_factor"] == 1.0
    assert m["max_dd_pct"] == pytest.approx(10 / 110)
    assert m["total_costs"] == pytest.approx(4)


def test_vectorised_lab_matches_single_path():
    from thunder.risk.recovery_lab import simulate_paths
    rng = np.random.default_rng(7)
    paths = rng.choice([-1.0, 1.5], size=(40, 120), p=[0.55, 0.45])
    for pol in ("A", "B", "C", "D"):
        v = simulate_paths(paths, pol, 3000.0 * 2)
        for i in range(40):
            s = simulate_path(paths[i], pol, 3000.0 * 2)
            assert v["end"][i] == pytest.approx(s["end"]), (pol, i)
            assert bool(v["killed"][i]) == s["killed"] and bool(v["ruined"][i]) == s["ruined"]
            assert v["longest"][i] == s["longest_losing"]
