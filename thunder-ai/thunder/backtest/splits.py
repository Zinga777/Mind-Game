"""Chronological 60/20/20 splits and rolling walk-forward windows (spec 13.2).

Features are computed causally over the whole history once, so a split can start
trading on its first bar without leaking: no indicator value at bar i depends on
anything after i (enforced by the truncation test).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Split:
    name: str
    start: int
    end: int


def chrono(n: int) -> dict[str, Split]:
    a = int(n * 0.6)
    b = int(n * 0.8)
    return {"train": Split("train", 0, a), "validation": Split("validation", a, b), "test": Split("test", b, n)}


def walk_forward(n: int, bars_per_month: int = 30 * 288, train_months: int = 3,
                 test_months: int = 1) -> list[tuple[int, int, int]]:
    """Return (train_start, test_start, test_end) windows stepping one month."""
    out = []
    tr, te = train_months * bars_per_month, test_months * bars_per_month
    s = 0
    while s + tr + te <= n:
        out.append((s, s + tr, s + tr + te))
        s += te
    return out
