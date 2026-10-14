"""The dashboard never runs trading logic: it writes rows to `commands`; the engine executes them."""
from __future__ import annotations

import json
import sqlite3

from ..db import now_ms

COMMANDS = {"START", "STOP", "SET_MODE", "RESET_PAPER", "EXPORT_STRATEGY", "HALT_RESET", "RUN_ARENA", "ADD_FUNDS",
            "CONFIRM_DEPOSIT", "RUN_INSIGHTS", "DOWNLOAD_DATA", "EXIT_ALL_HALT", "LOAD_DEMO"}


def submit(con: sqlite3.Connection, command: str, **args) -> int:
    if command not in COMMANDS:
        raise ValueError(f"unknown command {command}")
    cur = con.execute("INSERT INTO commands(ts,command,args_json,status) VALUES(?,?,?, 'pending')",
                      (now_ms(), command, json.dumps(args)))
    return int(cur.lastrowid)


def pending(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM commands WHERE status='pending' ORDER BY id").fetchall()


def finish(con: sqlite3.Connection, cid: int, ok: bool, result: str) -> None:
    con.execute("UPDATE commands SET status=?, result=?, done_at=? WHERE id=?",
                ("done" if ok else "failed", result[:2000], now_ms(), cid))


def status(con: sqlite3.Connection, cid: int) -> dict:
    r = con.execute("SELECT * FROM commands WHERE id=?", (cid,)).fetchone()
    return dict(r) if r else {}
