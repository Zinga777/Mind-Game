"""Reconciler: DB <-> memory every cycle; in live mode DB <-> exchange every 10 s.
Any mismatch => stop new entries, keep protective orders, HALT and alert (H14)."""
from __future__ import annotations

import json
import sqlite3

from ..db import integrity_ok, log_event


def check_paper(con: sqlite3.Connection, runners: dict) -> list[str]:
    problems = []
    if not integrity_ok(con):
        problems.append("database integrity check failed")
        return problems
    for acc_id, r in runners.items():
        row = con.execute("SELECT state_json FROM accounts WHERE account_id=?", (acc_id,)).fetchone()
        if row is None:
            continue
        st = json.loads(row[0])
        db_pos = st.get("pos") is not None
        if db_pos != (r.pos is not None):
            problems.append(f"{acc_id}: open-position mismatch between memory and database")
        if abs(st["account"]["equity"] - r.acct.equity) > 1e-6:
            problems.append(f"{acc_id}: equity mismatch between memory and database")
    return problems


def check_live(con: sqlite3.Connection, private, expected_pairs: set[str]) -> list[str]:
    problems = []
    try:
        on_exchange = {p.pair for p in private.positions()}
    except Exception as e:
        return [f"cannot read positions from exchange ({type(e).__name__})"]
    extra = on_exchange - expected_pairs
    missing = expected_pairs - on_exchange
    if extra:
        problems.append(f"exchange has positions the bot does not know about: {sorted(extra)}")
    if missing:
        problems.append(f"bot expects positions the exchange does not have: {sorted(missing)}")
    for p in problems:
        log_event(con, "HALT", "reconciler", p)
    return problems
