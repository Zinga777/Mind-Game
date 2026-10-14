"""Daily / on-demand plain-language insight report (spec 14.2), journal style."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

import numpy as np

from ..db import now_ms
from ..strategies import REGISTRY
from .buckets import bucket_table
from .mae_mfe import suggestions


def _trades(con: sqlite3.Connection, mode: str) -> list[dict]:
    rows = con.execute("SELECT * FROM trades WHERE mode=? ORDER BY exit_time", (mode,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["features"] = json.loads(d.pop("features_json") or "{}")
        d["side"] = d["side"]
        d["bars_held"] = int((d["exit_time"] - d["entry_time"]) / 300_000) if d["exit_time"] else 0
        out.append(d)
    return out


def analyst_scorecard(con: sqlite3.Connection, mode: str) -> list[dict]:
    """How often each analyst's direction matched the outcome; did counter-analyst warnings precede losses?"""
    rows = con.execute("SELECT c.reports_json, t.net_pnl, t.side FROM candidates c JOIN trades t ON t.strategy_id=c.strategy_id "
                       "AND t.instrument=c.instrument AND t.entry_time = c.candle_close_time AND t.mode=c.mode "
                       "WHERE c.mode=? AND c.state='QUALIFIED'", (mode,)).fetchall()
    stats: dict = defaultdict(lambda: [0, 0])
    warn = [0, 0]  # [warnings before losers, losers]
    for rj, pnl, side in rows:
        reps = (json.loads(rj) or {}).get("reports", [])
        win = pnl > 0
        for rep in reps:
            if rep["direction"] == "neutral":
                continue
            agrees = (rep["direction"] == "bullish") == (side == "long")
            if rep["analyst"] == "Counter-analyst":
                continue
            stats[rep["analyst"]][0] += int(agrees == win)
            stats[rep["analyst"]][1] += 1
        if not win:
            warn[1] += 1
            ctr = [r for r in reps if r["analyst"] == "Counter-analyst"]
            if ctr and ctr[0].get("contradictions"):
                warn[0] += 1
    out = [{"analyst": k, "matched": v[0], "calls": v[1], "hit_rate": v[0] / v[1] if v[1] else None} for k, v in stats.items()]
    out.append({"analyst": "Counter-analyst", "matched": warn[0], "calls": warn[1],
                "hit_rate": warn[0] / warn[1] if warn[1] else None, "note": "share of losing trades that had a specific warning"})
    return out


def generate(con: sqlite3.Connection, mode: str = "backtest", store: bool = True) -> dict:
    trades = _trades(con, mode)
    by_s: dict = defaultdict(list)
    for t in trades:
        by_s[t["strategy_id"]].append(t)
    lines = [f"# THUNDER insight report ({mode.upper()} results)", ""]
    if any(t.get("sample_data") for t in trades):
        lines += ["> **SAMPLE DATA** — these trades come from synthetic candles and say nothing about real markets.", ""]
    all_rows = []
    sugg_rows = []
    for sid, ts in sorted(by_s.items()):
        rows = bucket_table(ts)
        all_rows += [{**r, "strategy_id": sid} for r in rows]
        r = np.array([t["r_multiple"] for t in ts])
        name = REGISTRY[sid].name if sid in REGISTRY else sid
        lines.append(f"## {sid} {name} — {len(ts)} trades, {r.mean():+.2f}R average after costs")
        reg = [x for x in rows if x["bucket"] == "regime"]
        good = sorted([x for x in reg if x["mean_r"] > 0], key=lambda x: -x["mean_r"])
        bad = sorted([x for x in reg if x["mean_r"] <= 0], key=lambda x: x["mean_r"])
        for x in good[:2]:
            lines.append(f"- Worked in **{x['value']}**: {x['n']} trades, {x['mean_r']:+.2f}R "
                         f"(CI {x['ci_low']:+.2f} to {x['ci_high']:+.2f}) — {x['flag']}.")
        for x in bad[:2]:
            lines.append(f"- Lost money in **{x['value']}**: {x['mean_r']:+.2f}R, n={x['n']} — {x['flag']}.")
        hrs = sorted([x for x in rows if x["bucket"] == "hour_ist" and x["n"] >= 10], key=lambda x: x["mean_r"])
        if hrs and hrs[0]["mean_r"] < 0:
            lines.append(f"- Weakest time window: {hrs[0]['value']} ({hrs[0]['mean_r']:+.2f}R, n={hrs[0]['n']}).")
        for s in suggestions(ts):
            lines.append(f"- Suggestion (needs your review, never auto-applied): {s}")
            sugg_rows.append((sid, s))
        lines.append("")
    lines.append(f"_{len(all_rows)} buckets were examined. With this many comparisons some will look good by luck; "
                 "only CONFIRMED items (replicated in a later period) enter a strategy's checklist._")
    md = "\n".join(lines) if trades else "Nothing to show yet: the bot needs some trades before the first report."
    sc = analyst_scorecard(con, mode)
    if store:
        con.execute("INSERT INTO insights(ts,scope,report_md,buckets_json) VALUES(?,?,?,?)",
                    (now_ms(), mode, md, json.dumps({"rows": all_rows, "analysts": sc})))
        for sid, s in sugg_rows:
            if not con.execute("SELECT 1 FROM suggested_changes WHERE strategy_id=? AND suggestion=?", (sid, s)).fetchone():
                con.execute("INSERT INTO suggested_changes(ts,strategy_id,suggestion) VALUES(?,?,?)", (now_ms(), sid, s))
    return {"markdown": md, "rows": all_rows, "analysts": sc}


def to_html(md: str) -> str:
    import html
    body = []
    for line in md.splitlines():
        e = html.escape(line).replace("**", "")
        if line.startswith("# "):
            body.append(f"<h1>{e[2:]}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{e[3:]}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{e[2:]}</li>")
        elif line.strip():
            body.append(f"<p>{e}</p>")
    return ("<!doctype html><meta charset='utf-8'><title>THUNDER insight report</title>"
            "<style>body{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 16px;line-height:1.5}</style>"
            + "\n".join(body))
