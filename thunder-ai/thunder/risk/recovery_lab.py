"""Recovery Lab (spec 12): Monte-Carlo block bootstrap of a strategy's OOS net R-multiples,
applying each sizing policy. Policy D (Martingale) is a ruin demonstration only."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

POLICIES = ("A", "B", "C", "D")
NAMES = {"A": "Fixed risk", "B": "Capped recovery", "C": "De-risk after streak", "D": "Classic Martingale (ruin demo)"}


def block_bootstrap(r: np.ndarray, n_paths: int, length: int, block: int, rng: np.random.Generator) -> np.ndarray:
    out = np.empty((n_paths, length))
    nb = int(np.ceil(length / block))
    for p in range(n_paths):
        starts = rng.integers(0, max(1, len(r) - block + 1), size=nb)
        seq = np.concatenate([r[s:s + block] for s in starts])[:length]
        out[p] = seq
    return out


def simulate_path(r: np.ndarray, policy: str, equity0: float, risk_pct: float = 0.005, dd_kill: float = 0.10,
                  step: float = 0.25, cap: float = 1.5) -> dict:
    eq = equity0
    peak = equity0
    k = 0
    killed = False
    ruined = False
    max_dd = 0.0
    longest = 0
    cur_streak = 0
    recover_times = []
    dd_start = None
    recent: list[float] = []
    cooldown = 0
    for t, x in enumerate(r):
        if cooldown > 0:
            cooldown -= 1
            continue
        if policy == "A":
            m = 1.0
        elif policy == "C":
            m = 0.5 if k >= 3 else 1.0
        elif policy == "B":
            ok = len(recent) >= 10 and np.mean(recent) >= 0 and eq >= 0.9 * peak
            m = min(cap, 1 + step * k) if (k > 0 and ok) else 1.0
        else:  # D Martingale
            m = 2.0 ** k
        risk = eq * risk_pct * m
        if policy != "D":
            risk = min(risk, eq * 0.01)
        if risk > eq:
            ruined = True
            eq = 0.0
            break
        pnl = risk * x
        eq += pnl
        recent = (recent + [x])[-30:]
        if x < 0:
            k += 1; cur_streak += 1; longest = max(longest, cur_streak)
        else:
            k = 0; cur_streak = 0
        if policy == "B" and k >= 4:
            cooldown = 1; k = 0
        peak = max(peak, eq)
        dd = 1 - eq / peak if peak > 0 else 1
        if dd >= 0.05 and dd_start is None:
            dd_start = t
        if dd_start is not None and eq >= peak:
            recover_times.append(t - dd_start); dd_start = None
        max_dd = max(max_dd, dd)
        if dd >= dd_kill:
            killed = True
        if eq <= 0.5 * equity0:
            ruined = True
        if eq <= 0:
            break
    return {"end": eq, "killed": killed, "ruined": ruined, "max_dd": max_dd, "longest_losing": longest,
            "recover_trades": float(np.mean(recover_times)) if recover_times else np.nan}


@dataclass
class LabResult:
    table: dict
    recommendation: str
    b_allowed: bool
    fan: dict


def run_lab(r_oos: np.ndarray, equity0: float, risk_pct: float = 0.005, n_paths: int = 10_000,
            length: int | None = None, block: int = 5, seed: int = 42) -> LabResult:
    r_oos = np.asarray(r_oos, dtype=float)
    if len(r_oos) < 10:
        return LabResult({}, "Not enough out-of-sample trades to run the Recovery Lab (need 10+). Use A: fixed risk.",
                         False, {})
    rng = np.random.default_rng(seed)
    length = length or max(100, len(r_oos))
    paths = block_bootstrap(r_oos, n_paths, length, block, rng)
    table, fan = {}, {}
    for pol in POLICIES:
        res = [simulate_path(p, pol, equity0, risk_pct) for p in paths]
        ends = np.array([x["end"] for x in res])
        table[pol] = {
            "name": NAMES[pol],
            "median_end": float(np.median(ends)),
            "p5_end": float(np.percentile(ends, 5)),
            "p_kill": float(np.mean([x["killed"] for x in res])),
            "p_ruin": float(np.mean([x["ruined"] for x in res])),
            "longest_losing_median": float(np.median([x["longest_losing"] for x in res])),
            "avg_recover_trades": float(np.nanmean([x["recover_trades"] for x in res])) if any(
                np.isfinite(x["recover_trades"]) for x in res) else float("nan"),
        }
        fan[pol] = [float(np.percentile(ends, q)) for q in (5, 25, 50, 75, 95)]
    a, b = table["A"], table["B"]
    b_ok = b["median_end"] > a["median_end"] and b["p5_end"] > a["p5_end"] and b["p_kill"] <= a["p_kill"] + 0.02
    if b_ok:
        rec = ("B (capped recovery) improved both the typical and the bad-case outcome without raising the "
               "chance of hitting the 10% kill-switch by more than 2 points. It may be selected (never in the first live stage).")
    else:
        rec = ("Recommended: A (fixed risk). Capped recovery did not improve both the typical and the bad-case outcome "
               "safely. Sizing rules cannot create an edge; they only change how much is lost when losses come.")
    return LabResult(table, rec, b_ok, fan)
