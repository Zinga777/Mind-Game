"""Forward paper evidence for the PAPER_PROVEN gate (spec 13.4)."""
from __future__ import annotations

import sqlite3

import numpy as np

from ..backtest import promotion
from ..config.schema import Config
from ..db import kv_get


def paper_evidence(con: sqlite3.Connection, strategy_id: str) -> dict:
    rows = con.execute("SELECT r_multiple, entry_time, exit_time, slippage, realised_risk FROM trades "
                       "WHERE mode='paper' AND strategy_id=? ORDER BY exit_time", (strategy_id,)).fetchall()
    n = len(rows)
    days = (rows[-1][2] - rows[0][1]) / 86_400_000 if n else 0.0
    r = np.array([x[0] for x in rows]) if n else np.array([])
    slip_paper = float(np.mean([x[3] / x[4] for x in rows if x[4]])) if n else 0.0
    bt = con.execute("SELECT AVG(slippage / realised_risk) FROM trades WHERE mode='backtest' AND strategy_id=? AND realised_risk>0",
                     (strategy_id,)).fetchone()[0]
    within = bool(bt) and n > 0 and abs(slip_paper - bt) <= 0.3 * bt
    hours = kv_get(con, "uptime_hours", []) or []
    up = len(set(hours)) / max(1, (hours[-1] - hours[0] + 1)) if hours else 0.0
    recon = con.execute("SELECT COUNT(*) FROM events WHERE source='reconciler' AND level='HALT'").fetchone()[0]
    return {"paper_days": days, "paper_trades": n, "paper_expectancy": float(r.mean()) if n else 0.0,
            "slippage_within": within, "uptime": up, "recon_errors": recon}


def status_with_paper(con: sqlite3.Connection, cfg: Config, strategy_id: str, summary: dict) -> str:
    ev = {**summary.get("evidence", {}), **paper_evidence(con, strategy_id)}
    return promotion.evaluate(ev, cfg.gates).status
