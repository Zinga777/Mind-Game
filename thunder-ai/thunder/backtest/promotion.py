"""Promotion ladder (spec 13.4). Every gate is evaluated on OUT-OF-SAMPLE data and
returned as a plain-language checklist (gate, passed, detail)."""
from __future__ import annotations

from dataclasses import dataclass, field

RESEARCH, CANDIDATE, CONFIRMED, PAPER_PROVEN, LIVE_ELIGIBLE = (
    "RESEARCH", "CANDIDATE", "CONFIRMED_BACKTEST", "PAPER_PROVEN", "LIVE_ELIGIBLE")
LADDER = [RESEARCH, CANDIDATE, CONFIRMED, PAPER_PROVEN, LIVE_ELIGIBLE]

NO_EDGE_MESSAGE = "No strategy has shown a net edge yet. This is normal; most don't. Keeping real money out."


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass
class Verdict:
    status: str
    tentative: bool
    gates: list[Gate] = field(default_factory=list)
    plain: str = ""


def evaluate(ev: dict, gates_cfg) -> Verdict:
    """ev keys: oos_trades, oos_expectancy_r, oos_pf, oos_max_dd, q_value, ci_low, exp_cost15,
    exp_minus_best3, neighbour_share, max_month_share, both_instruments (bool|None),
    paper_days, paper_trades, paper_expectancy, slippage_within, uptime, recon_errors, owner_action."""
    g: list[Gate] = []
    n = ev.get("oos_trades", 0)
    add = lambda name, ok, d: g.append(Gate(name, bool(ok), d))
    add("Enough out-of-sample trades", n >= gates_cfg.min_oos_trades,
        f"{n} trades (need {gates_cfg.min_oos_trades}; {gates_cfg.tentative_oos_trades}-{gates_cfg.min_oos_trades - 1} = tentative)")
    add("Positive net expectancy", ev.get("oos_expectancy_r", 0) > 0, f"{ev.get('oos_expectancy_r', 0):+.3f}R per trade after all costs")
    add("Profit factor >= %.1f" % gates_cfg.min_profit_factor, ev.get("oos_pf", 0) >= gates_cfg.min_profit_factor,
        f"profit factor {ev.get('oos_pf', 0):.2f}")
    add("Max drawdown <= %.0f%%" % (gates_cfg.max_dd * 100), ev.get("oos_max_dd", 1) <= gates_cfg.max_dd,
        f"worst drop {ev.get('oos_max_dd', 0):.1%}")
    add("Beats random entry (corrected p < %.2f)" % gates_cfg.p_value, ev.get("q_value", 1) < gates_cfg.p_value,
        f"corrected p = {ev.get('q_value', 1):.3f}")
    cand_ok = all(x.passed for x in g[1:]) and n >= gates_cfg.tentative_oos_trades
    tentative = n < gates_cfg.min_oos_trades
    status = RESEARCH
    if cand_ok and n >= gates_cfg.min_oos_trades:
        status = CANDIDATE
    # CONFIRMED_BACKTEST gates
    c: list[Gate] = []
    addc = lambda name, ok, d: c.append(Gate(name, bool(ok), d))
    addc("95% confidence interval above zero", ev.get("ci_low", -1) > 0, f"lower bound {ev.get('ci_low', float('nan')):+.3f}R")
    addc("Still positive with costs x1.5", ev.get("exp_cost15", -1) > 0, f"{ev.get('exp_cost15', float('nan')):+.3f}R")
    addc("Still positive without the best 3 trades", ev.get("exp_minus_best3", -1) > 0,
         f"{ev.get('exp_minus_best3', float('nan')):+.3f}R")
    addc(">= 70% of neighbouring settings also positive", ev.get("neighbour_share", 0) >= 0.7,
         f"{ev.get('neighbour_share', 0):.0%} of neighbours positive")
    addc("No single month > 40% of profit", ev.get("max_month_share", 1) <= 0.4, f"largest month {ev.get('max_month_share', 0):.0%}")
    both = ev.get("both_instruments")
    addc("Positive on BTC and ETH (or labelled instrument-specific)", both is not False,
         "positive on both" if both else ("instrument-specific" if both is None else "not positive on both"))
    g += c
    if status == CANDIDATE and all(x.passed for x in c):
        status = CONFIRMED
    p: list[Gate] = []
    addp = lambda name, ok, d: p.append(Gate(name, bool(ok), d))
    addp(">= %d days and >= %d forward paper trades" % (gates_cfg.paper_days, gates_cfg.paper_trades),
         ev.get("paper_days", 0) >= gates_cfg.paper_days and ev.get("paper_trades", 0) >= gates_cfg.paper_trades,
         f"{ev.get('paper_days', 0):.0f} days, {ev.get('paper_trades', 0)} trades")
    addp("Paper net expectancy > 0", ev.get("paper_expectancy", 0) > 0, f"{ev.get('paper_expectancy', 0):+.3f}R")
    addp("Paper slippage/fills within 30% of backtest", ev.get("slippage_within", False), "compared to assumptions")
    measured = "paper_trades" in ev
    addp("Engine uptime >= 95%", measured and ev.get("uptime", 0) >= 0.95,
         f"{ev.get('uptime', 0):.0%}" if measured else "not measured yet (needs forward paper trading)")
    addp("No unresolved reconciliation errors", measured and ev.get("recon_errors", 1) == 0,
         f"{ev.get('recon_errors', 0)} open" if measured else "not measured yet")
    g += p
    if status == CONFIRMED and all(x.passed for x in p):
        status = PAPER_PROVEN
        if ev.get("owner_action"):
            status = LIVE_ELIGIBLE
    plain = {
        RESEARCH: "Not proven. It has not shown a reliable edge after costs on unseen data.",
        CANDIDATE: "Promising on unseen data, but not yet confirmed by the stress tests.",
        CONFIRMED: "Passed the backtest stress tests. Needs 30+ days of forward paper trading next.",
        PAPER_PROVEN: "Backtest and forward paper results agree. May be selected for live (owner decision).",
        LIVE_ELIGIBLE: "Selected by the owner for live trading.",
    }[status]
    if tentative and status == RESEARCH and n >= gates_cfg.tentative_oos_trades and all(x.passed for x in g[1:5]):
        plain = "TENTATIVE: looks positive but on too few trades to trust."
    if getattr(gates_cfg, "relaxed", False):
        plain += " (RELAXED GATES — results tagged)"
    return Verdict(status, tentative, g, plain)
