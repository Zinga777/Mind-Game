"""Qualification protocol (spec 9.4): detector -> analysts -> one challenge round
-> scorecard -> hard disqualification -> final state.

States: QUALIFIED, WAIT, DISQUALIFIED, RISK_REJECTED (set later by the risk guard).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..strategies.base import Candidate, Features
from ..trade.builder import TradePlan
from . import analysts as A
from .scorecard import score

QUALIFIED, WAIT, DISQUALIFIED, RISK_REJECTED = "QUALIFIED", "WAIT", "DISQUALIFIED", "RISK_REJECTED"


@dataclass
class DeskResult:
    state: str
    reason: str
    score: float
    components: dict
    reports: list[dict] = field(default_factory=list)
    challenge: list[str] = field(default_factory=list)
    llm: Optional[dict] = None


def challenge_round(reports: dict) -> list[str]:
    """One round: pairs argue, lead resolves by predefined rules. Returns notes."""
    notes = []
    t, v, lv, ctr = reports["trend"], reports["volume_momentum"], reports["levels"], reports["counter"]
    if t.direction == "neutral" and v.direction != "neutral":
        notes.append("Trend vs volume: volume is active but structure is unclear -> trend analyst leads (no upgrade).")
    if lv.contradictions:
        notes.append("Levels vs obstacles: " + lv.contradictions[0] + " -> score reduced, target kept.")
    if ctr.contradictions:
        notes.append("Counter-analyst: " + ctr.contradictions[0])
    return notes


def evaluate(F: Features, i: int, c: Candidate, plan: Optional[TradePlan], threshold: int,
             regime_validated: bool = True, data_ok: bool = True) -> DeskResult:
    reps = {
        "candlestick": A.candlestick(F, i, c),
        "trend": A.trend_structure(F, i, c),
        "volume_momentum": A.volume_momentum(F, i, c),
        "levels": A.levels_liquidity(F, i, c),
        "psychology": A.psychology(F, i, c),
        "execution": A.execution_cost(
            (plan.costs.cost_r + plan.funding_cost_r) if plan and plan.costs else None,
            plan.costs.rr_net if plan and plan.costs else None),
    }
    reps["counter"] = A.counter_analyst(list(reps.values()), c)
    total, comp = score(reps)
    notes = challenge_round(reps)
    out = [r.to_dict() for r in reps.values()]
    # hard disqualification (cannot be bought back with score)
    if not data_ok:
        return DeskResult(DISQUALIFIED, "stale or inconsistent data", total, comp, out, notes)
    if plan is None or not plan.ok:
        return DeskResult(DISQUALIFIED, plan.reason if plan else "no plan", total, comp, out, notes)
    if not regime_validated:
        return DeskResult(WAIT, f"strategy not validated for regime {c.regime}", total, comp, out, notes)
    if any("chasing" in x for x in reps["psychology"].contradictions):
        return DeskResult(DISQUALIFIED, "chasing: entry too far from base (FOMO filter)", total, comp, out, notes)
    if any("panic candle" in x or "buying climax" in x for x in reps["psychology"].contradictions):
        return DeskResult(WAIT, "climax candle: wait for a tested confirmation", total, comp, out, notes)
    if total < threshold:
        return DeskResult(DISQUALIFIED, f"score {total:.0f} below threshold {threshold}", total, comp, out, notes)
    return DeskResult(QUALIFIED, "all desk checks passed", total, comp, out, notes)
