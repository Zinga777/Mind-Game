"""Performance metrics, all NET of costs (gross shown separately). Spec 13.3."""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

BARS_PER_YEAR_5M = 365 * 288   # crypto trades 24/7


def bootstrap_ci(x: np.ndarray, n: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def max_drawdown(eq: np.ndarray) -> tuple[float, float]:
    if len(eq) == 0:
        return 0.0, 0.0
    peak = np.maximum.accumulate(eq)
    dd = 1 - eq / peak
    i = int(np.argmax(dd))
    return float(dd[i]), float(peak[i] - eq[i])


def longest_streak(r: np.ndarray, losing: bool = True) -> int:
    best = cur = 0
    for v in r:
        if (v < 0) if losing else (v > 0):
            cur += 1; best = max(best, cur)
        else:
            cur = 0
    return best


def compute(trades: list[dict], equity_curve: list[tuple[int, float]], equity0: float,
            candidates: list[dict] | None = None, bars: int | None = None) -> dict:
    r = np.array([t["r_multiple"] for t in trades], dtype=float)
    net = np.array([t["net_pnl"] for t in trades], dtype=float)
    gross = np.array([t["gross_pnl"] for t in trades], dtype=float)
    eq = np.array([e for _, e in equity_curve], dtype=float) if equity_curve else np.array([equity0])
    n = len(trades)
    wins, losses = net[net > 0], net[net <= 0]
    pf = (wins.sum() / -losses.sum()) if losses.sum() < 0 else (float("inf") if wins.sum() > 0 else 0.0)
    dd_pct, dd_inr = max_drawdown(eq)
    rets = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
    sd = rets.std()
    sharpe = float(rets.mean() / sd * math.sqrt(BARS_PER_YEAR_5M)) if sd > 0 else 0.0
    dn = rets[rets < 0]
    sortino = float(rets.mean() / dn.std() * math.sqrt(BARS_PER_YEAR_5M)) if len(dn) > 1 and dn.std() > 0 else 0.0
    lo, hi = bootstrap_ci(r) if n >= 2 else (float("nan"), float("nan"))
    days = ((equity_curve[-1][0] - equity_curve[0][0]) / 86_400_000) if len(equity_curve) > 1 else 0
    in_mkt = sum(t.get("bars_held", 0) for t in trades)
    months: Counter = Counter()
    for t in trades:
        months[int(t["exit_time"] // (30 * 86_400_000))] += t["net_pnl"]
    tot_pos = sum(v for v in months.values() if v > 0)
    max_month_share = (max(months.values()) / tot_pos) if tot_pos > 0 and months else 0.0
    rej = Counter(c["reason"] for c in (candidates or []) if c.get("state") != "QUALIFIED")
    return {
        "trades": n,
        "win_rate": float((net > 0).mean()) if n else 0.0,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "expectancy_inr": float(net.mean()) if n else 0.0,
        "expectancy_r": float(r.mean()) if n else 0.0,
        "expectancy_r_ci": [lo, hi],
        "net_pnl": float(net.sum()),
        "gross_pnl": float(gross.sum()),
        "total_costs": float((gross - net).sum()),
        "net_return": float(net.sum() / equity0),
        "profit_factor": float(pf) if np.isfinite(pf) else 99.0,
        "max_dd_pct": dd_pct,
        "max_dd_inr": dd_inr,
        "longest_losing_streak": longest_streak(r),
        "time_in_market": float(in_mkt / bars) if bars else 0.0,
        "avg_cost_r": float(np.mean([(t["gross_pnl"] - t["net_pnl"]) / t["realised_risk"] for t in trades
                                     if t["realised_risk"] > 0])) if n else 0.0,
        "sharpe": sharpe,
        "sortino": sortino,
        "trades_per_day": n / days if days > 0 else 0.0,
        "days": days,
        "mae_r_avg": float(np.mean([t["mae_r"] for t in trades])) if n else 0.0,
        "mfe_r_avg": float(np.mean([t["mfe_r"] for t in trades])) if n else 0.0,
        "max_month_profit_share": float(max_month_share),
        "rejections": dict(rej.most_common(12)),
        "candidates": len(candidates or []),
    }


def benjamini_hochberg(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, float]:
    """Return BH-adjusted p-values (q-values)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj = {}
    prev = 1.0
    for rank in range(m, 0, -1):
        k, p = items[rank - 1]
        q = min(prev, p * m / rank)
        adj[k] = q
        prev = q
    return adj


def permutation_pvalue(strategy_r: np.ndarray, control_r: np.ndarray, n: int = 5000, seed: int = 0) -> float:
    """One-sided two-sample permutation test: H1 mean(strategy) > mean(control)."""
    a, b = np.asarray(strategy_r, float), np.asarray(control_r, float)
    if len(a) < 2 or len(b) < 2:
        return 1.0
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n):
        rng.shuffle(pool)
        if pool[:len(a)].mean() - pool[len(a):].mean() >= obs:
            cnt += 1
    return (cnt + 1) / (n + 1)
