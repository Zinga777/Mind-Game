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


def simulate_paths(paths: np.ndarray, policy: str, equity0: float, risk_pct: float = 0.005, dd_kill: float = 0.10,
                   step: float = 0.25, cap: float = 1.5) -> dict:
    """Vectorised over paths; same rules as simulate_path (tested to agree)."""
    n, T = paths.shape
    eq = np.full(n, equity0)
    peak = eq.copy()
    k = np.zeros(n, dtype=int)
    streak = np.zeros(n, dtype=int)
    longest = np.zeros(n, dtype=int)
    killed = np.zeros(n, dtype=bool)
    ruined = np.zeros(n, dtype=bool)
    dead = np.zeros(n, dtype=bool)
    cooldown = np.zeros(n, dtype=int)
    hist = np.full((n, 30), np.nan)
    hn = np.zeros(n, dtype=int)
    dd_start = np.full(n, -1)
    rec_sum = np.zeros(n)
    rec_cnt = np.zeros(n)
    for t in range(T):
        x = paths[:, t]
        active = ~dead & (cooldown == 0)
        cooldown = np.where(~dead & (cooldown > 0), cooldown - 1, cooldown)
        if policy == "A":
            m = np.ones(n)
        elif policy == "C":
            m = np.where(k >= 3, 0.5, 1.0)
        elif policy == "B":
            cnt = np.minimum(hn, 30)
            mean = np.where(cnt > 0, np.nansum(hist, axis=1) / np.maximum(cnt, 1), 0.0)
            ok = (cnt >= 10) & (mean >= 0) & (eq >= 0.9 * peak)
            m = np.where((k > 0) & ok, np.minimum(cap, 1 + step * k), 1.0)
        else:
            m = 2.0 ** k
        risk = eq * risk_pct * m
        if policy != "D":
            risk = np.minimum(risk, eq * 0.01)
        broke = active & (risk > eq)
        ruined |= broke
        eq = np.where(broke, 0.0, eq)
        dead |= broke
        go = active & ~broke
        eq = np.where(go, eq + risk * x, eq)
        hist[go, (hn[go] % 30)] = x[go]
        hn = np.where(go, hn + 1, hn)
        loss = go & (x < 0)
        win = go & (x >= 0)
        k = np.where(loss, k + 1, np.where(win, 0, k))
        streak = np.where(loss, streak + 1, np.where(win, 0, streak))
        longest = np.maximum(longest, streak)
        if policy == "B":
            cd = go & (k >= 4)
            cooldown = np.where(cd, 1, cooldown)
            k = np.where(cd, 0, k)
        peak = np.where(go, np.maximum(peak, eq), peak)
        dd = np.where(peak > 0, 1 - eq / peak, 1.0)
        start = go & (dd >= 0.05) & (dd_start < 0)
        dd_start = np.where(start, t, dd_start)
        rec = go & (dd_start >= 0) & (eq >= peak)
        rec_sum = np.where(rec, rec_sum + (t - dd_start), rec_sum)
        rec_cnt = np.where(rec, rec_cnt + 1, rec_cnt)
        dd_start = np.where(rec, -1, dd_start)
        killed |= go & (dd >= dd_kill)
        ruined |= go & (eq <= 0.5 * equity0)
        dead |= eq <= 0
    rec_avg = np.where(rec_cnt > 0, rec_sum / np.maximum(rec_cnt, 1), np.nan)
    return {"end": eq, "killed": killed, "ruined": ruined, "longest": longest, "recover": rec_avg}


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
        res = simulate_paths(paths, pol, equity0, risk_pct)
        ends = res["end"]
        table[pol] = {
            "name": NAMES[pol],
            "median_end": float(np.median(ends)),
            "p5_end": float(np.percentile(ends, 5)),
            "p_kill": float(res["killed"].mean()),
            "p_ruin": float(res["ruined"].mean()),
            "longest_losing_median": float(np.median(res["longest"])),
            "avg_recover_trades": float(np.nanmean(res["recover"])) if np.isfinite(res["recover"]).any() else float("nan"),
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
