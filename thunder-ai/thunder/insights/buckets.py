"""Pre-registered insight buckets (spec 14.2). The list is FIXED in code; the report
states how many buckets were examined so readers can discount lucky ones."""
from __future__ import annotations

import numpy as np

from ..backtest.metrics import bootstrap_ci


def _num(t, k):
    v = (t.get("features") or {}).get(k)
    return v if isinstance(v, (int, float)) and v is not None and np.isfinite(v) else None


def _cut(v, edges, labels):
    if v is None:
        return None
    for e, lab in zip(edges, labels):
        if v < e:
            return lab
    return labels[-1]


BUCKETS = {
    "regime": lambda t: t.get("regime"),
    "hour_ist": lambda t: (lambda h: None if h is None else f"{int(h)//4*4:02d}-{int(h)//4*4+4:02d} IST")(_num(t, "hour_ist")),
    "weekday": lambda t: (lambda d: None if d is None else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(d)])(_num(t, "weekday")),
    "session": lambda t: (t.get("features") or {}).get("session"),
    "volume_z": lambda t: _cut(_num(t, "vol_z"), [0, 1, 2], ["below normal", "normal", "high", "very high"]),
    "dist_to_level": lambda t: _cut(_num(t, "dist_sup_atr") if t.get("side") == "long" else _num(t, "dist_res_atr"),
                                    [0.5, 1.5, 3], ["at level (<0.5 ATR)", "near", "far", "very far"]),
    "pattern": lambda t: ",".join((t.get("features") or {}).get("patterns", [])) or "none",
    "score": lambda t: _cut(t.get("score"), [70, 80, 90], ["<70", "70-79", "80-89", "90+"]),
    "cost_r": lambda t: _cut((t["gross_pnl"] - t["net_pnl"]) / t["realised_risk"] if t.get("realised_risk") else None,
                             [0.1, 0.2, 0.3], ["<0.10R", "0.10-0.20R", "0.20-0.30R", ">0.30R"]),
    "holding": lambda t: _cut(t.get("bars_held"), [12, 48, 144], ["<1h", "1-4h", "4-12h", "12h+"]),
    "exit_reason": lambda t: t.get("exit_reason"),
    "direction": lambda t: t.get("side"),
}


def bucket_table(trades: list[dict], min_obs: int = 100, seed: int = 0) -> list[dict]:
    """Every row: bucket, value, n, mean R, CI, flag. CONFIRMED = positive in the first half (n>=min_obs/2)
    AND replicated positive in the later half of the sample."""
    rows = []
    trades = sorted(trades, key=lambda t: t["exit_time"])
    half = len(trades) // 2
    for b, fn in BUCKETS.items():
        groups: dict = {}
        for idx, t in enumerate(trades):
            v = fn(t)
            if v is None:
                continue
            groups.setdefault(v, []).append((idx, t["r_multiple"]))
        for v, items in groups.items():
            r = np.array([x for _, x in items])
            first = np.array([x for i, x in items if i < half])
            later = np.array([x for i, x in items if i >= half])
            lo, hi = bootstrap_ci(r, n=1000, seed=seed) if len(r) > 1 else (np.nan, np.nan)
            n = len(r)
            flag = "TENTATIVE"
            if n >= min_obs:
                flag = "OBSERVED"
            if len(first) >= 30 and len(later) >= 30 and np.sign(first.mean()) == np.sign(later.mean()) and lo > 0:
                flag = "CONFIRMED"
            rows.append({"bucket": b, "value": str(v), "n": n, "mean_r": float(r.mean()), "ci_low": float(lo),
                         "ci_high": float(hi), "flag": flag})
    return rows


def n_buckets(rows: list[dict]) -> int:
    return len(rows)
