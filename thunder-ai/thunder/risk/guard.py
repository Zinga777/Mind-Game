"""Independent risk guard (spec 11.5). Runs AFTER the desk. MUST NOT import strategy code.

Checks in order; the first failure is recorded:
kill-switch -> data freshness -> daily loss stop -> open-position limit -> sizing feasibility
-> margin/liquidation -> cost_R and RR_net -> instrument tradable -> correlated exposure
-> blackout window -> LLM veto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..exchanges.base import InstrumentSpec
from ..trade.sizing import SizeResult, stop_within_liq_limit


@dataclass
class GuardInput:
    halted: bool
    data_fresh: bool
    daily_stop_hit: bool
    open_positions: int
    max_open_positions: int
    size: SizeResult
    entry: float
    stop: float
    leverage_for_liq: float
    spec: InstrumentSpec
    cost_r: float
    rr_net: float
    max_cost_r: float
    min_rr_net: float
    correlated_open: int = 0
    in_blackout: bool = False
    llm_verdict: Optional[str] = None
    cooldown_active: bool = False
    stop_to_liq_max_fraction: float = 0.5


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""
    checks: list[tuple[str, bool]] = field(default_factory=list)


def check(g: GuardInput) -> GuardResult:
    seq = [
        ("kill-switch", not g.halted, "kill-switch is active (HALTED)"),
        ("data freshness", g.data_fresh, "market data is stale or has gaps"),
        ("daily loss stop", not g.daily_stop_hit, "daily loss limit reached"),
        ("cooldown", not g.cooldown_active, "cooling down after a losing streak"),
        ("open positions", g.open_positions < g.max_open_positions, "position limit reached"),
        ("sizing", g.size.ok, g.size.reason or "cannot size this trade"),
        ("liquidation distance", stop_within_liq_limit(g.entry, g.stop, max(g.leverage_for_liq, 1.0),
                                                       g.spec.maintenance_margin_rate, g.stop_to_liq_max_fraction),
         "stop sits too close to the liquidation price"),
        ("costs", g.cost_r <= g.max_cost_r and g.rr_net >= g.min_rr_net, "costs vs reward not acceptable"),
        ("tradable", g.spec.status == "active", "instrument is not tradable"),
        ("correlated exposure", g.correlated_open == 0 or g.max_open_positions > 1, "correlated position already open"),
        ("blackout window", not g.in_blackout, "inside a no-trade time window"),
        ("LLM veto", g.llm_verdict != "veto", "LLM council vetoed"),
    ]
    done = []
    for name, passed, why in seq:
        done.append((name, bool(passed)))
        if not passed:
            return GuardResult(False, why, done)
    return GuardResult(True, "", done)


def in_blackout(ts_ms: int, windows: list[str]) -> bool:
    """windows like '23:55-00:05' in UTC."""
    mins = (ts_ms // 60_000) % 1440
    for w in windows:
        a, b = w.split("-")
        s = int(a[:2]) * 60 + int(a[3:])
        e = int(b[:2]) * 60 + int(b[3:])
        if (s <= e and s <= mins < e) or (s > e and (mins >= s or mins < e)):
            return True
    return False
