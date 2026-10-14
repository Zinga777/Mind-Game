"""Transparent 100-point scorecard (spec 9.4 step 4). A ranking tool, not a probability."""
from __future__ import annotations

WEIGHTS = {
    "trend_structure": 25,
    "location_levels": 20,
    "candlestick": 15,
    "volume": 15,
    "momentum_volatility": 10,
    "reward_vs_risk": 10,
    "cost_liquidity": 5,
}


def score(reports: dict) -> tuple[float, dict]:
    """reports: name -> AnalystReport. Returns (total, components)."""
    vm = reports["volume_momentum"].points  # 0..25 split volume 15 / momentum 10
    ex = reports["execution"].points        # 0..15 split RR 10 / cost 5
    comp = {
        "trend_structure": min(reports["trend"].points, 25),
        "location_levels": min(reports["levels"].points, 20),
        "candlestick": min(reports["candlestick"].points, 15),
        "volume": min(vm * 15 / 25, 15),
        "momentum_volatility": min(vm * 10 / 25, 10),
        "reward_vs_risk": min(ex * 10 / 15, 10),
        "cost_liquidity": min(ex * 5 / 15, 5),
    }
    return round(sum(comp.values()), 1), {k: round(v, 1) for k, v in comp.items()}
