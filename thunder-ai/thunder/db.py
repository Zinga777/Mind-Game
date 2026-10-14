"""SQLite storage (WAL) with versioned migrations (spec Section 19).

Every result table carries a `mode` column (backtest | paper | live) so results
are never mixed (H11). Unique constraints implement idempotency keys.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config.loader import data_dir

SCHEMA_VERSION = 1

MIGRATIONS: dict[int, str] = {
    1: """
CREATE TABLE IF NOT EXISTS instruments(pair TEXT PRIMARY KEY, spec_json TEXT, verified INTEGER, fetched_at INTEGER);
CREATE TABLE IF NOT EXISTS candles(instrument TEXT, timeframe TEXT, open_time_utc INTEGER, open REAL, high REAL,
    low REAL, close REAL, volume REAL, source TEXT, fetched_at INTEGER, quarantined INTEGER DEFAULT 0,
    PRIMARY KEY(instrument, timeframe, open_time_utc));
CREATE TABLE IF NOT EXISTS orderbook_snapshots(id INTEGER PRIMARY KEY, instrument TEXT, ts INTEGER, spread_bps REAL,
    depth_010 REAL, depth_025 REAL, imbalance REAL, raw_json TEXT);
CREATE TABLE IF NOT EXISTS funding(instrument TEXT, ts INTEGER, rate REAL, PRIMARY KEY(instrument, ts));
CREATE TABLE IF NOT EXISTS data_quality(id INTEGER PRIMARY KEY, instrument TEXT, timeframe TEXT, ts INTEGER, report_json TEXT);
CREATE TABLE IF NOT EXISTS features_cache(instrument TEXT, timeframe TEXT, ts INTEGER, json TEXT, PRIMARY KEY(instrument,timeframe,ts));
CREATE TABLE IF NOT EXISTS regimes(instrument TEXT, ts INTEGER, regime TEXT, PRIMARY KEY(instrument, ts));
CREATE TABLE IF NOT EXISTS strategies(strategy_id TEXT PRIMARY KEY, name TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS strategy_versions(strategy_id TEXT, version TEXT, params_json TEXT, code_hash TEXT,
    contaminated INTEGER DEFAULT 0, test_accesses INTEGER DEFAULT 0, PRIMARY KEY(strategy_id, version));
CREATE TABLE IF NOT EXISTS strategy_runs(run_id TEXT PRIMARY KEY, mode TEXT, strategy_id TEXT, instrument TEXT,
    split TEXT, params_json TEXT, config_hash TEXT, seed INTEGER, data_hash TEXT, code_version TEXT,
    started_at INTEGER, finished_at INTEGER, metrics_json TEXT, trial_count INTEGER, sample_data INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY, mode TEXT, run_id TEXT, account_id TEXT, strategy_id TEXT,
    instrument TEXT, candle_close_time INTEGER, direction TEXT, state TEXT, reason TEXT, score REAL,
    components_json TEXT, reports_json TEXT, llm_json TEXT, regime TEXT,
    UNIQUE(mode, run_id, strategy_id, instrument, candle_close_time));
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, mode TEXT, account_id TEXT, strategy_id TEXT, instrument TEXT,
    timeframe TEXT, candle_close_time INTEGER, decision TEXT, trace_json TEXT,
    UNIQUE(mode, account_id, strategy_id, instrument, timeframe, candle_close_time));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, mode TEXT, account_id TEXT, client_order_id TEXT UNIQUE,
    exchange_order_id TEXT, instrument TEXT, side TEXT, order_type TEXT, qty REAL, price REAL, stop_price REAL,
    status TEXT, created_at INTEGER, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS fills(id INTEGER PRIMARY KEY, mode TEXT, client_order_id TEXT, price REAL, qty REAL, fee REAL, ts INTEGER);
CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, mode TEXT, run_id TEXT, account_id TEXT, strategy_id TEXT,
    instrument TEXT, side TEXT, entry_time INTEGER, exit_time INTEGER, entry REAL, exit REAL, qty REAL, stop REAL,
    target REAL, exit_reason TEXT, gross_pnl REAL, fee_entry REAL, fee_exit REAL, gst REAL, slippage REAL,
    funding REAL, net_pnl REAL, r_multiple REAL, planned_risk REAL, realised_risk REAL, regime TEXT, score REAL,
    mae_r REAL, mfe_r REAL, features_json TEXT, trace_json TEXT, sample_data INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_trades_strat ON trades(mode, strategy_id, exit_time);
CREATE TABLE IF NOT EXISTS equity_curve(mode TEXT, account_id TEXT, ts INTEGER, equity REAL, peak REAL,
    net_cash_flows REAL, PRIMARY KEY(mode, account_id, ts));
CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY, mode TEXT, strategy_id TEXT, instrument TEXT,
    params_json TEXT, starting_equity REAL, state_json TEXT, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS cash_flows(id INTEGER PRIMARY KEY, mode TEXT, account_id TEXT, ts INTEGER, amount REAL,
    kind TEXT, source TEXT, confirmed_by_owner INTEGER);
CREATE TABLE IF NOT EXISTS risk_events(id INTEGER PRIMARY KEY, mode TEXT, account_id TEXT, ts INTEGER, kind TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS recovery_state(account_id TEXT PRIMARY KEY, policy TEXT, consecutive_losses INTEGER,
    multiplier REAL, cooldown_until INTEGER);
CREATE TABLE IF NOT EXISTS insights(id INTEGER PRIMARY KEY, ts INTEGER, scope TEXT, report_md TEXT, buckets_json TEXT);
CREATE TABLE IF NOT EXISTS suggested_changes(id INTEGER PRIMARY KEY, ts INTEGER, strategy_id TEXT, suggestion TEXT,
    status TEXT DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS strategy_cards(card_id TEXT PRIMARY KEY, strategy_id TEXT, version TEXT, status TEXT,
    card_json TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY, ts INTEGER, command TEXT, args_json TEXT,
    status TEXT DEFAULT 'pending', result TEXT, done_at INTEGER);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts INTEGER, level TEXT, source TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS heartbeat(name TEXT PRIMARY KEY, ts INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS settings_audit(id INTEGER PRIMARY KEY, ts INTEGER, key TEXT, old TEXT, new TEXT);
CREATE TABLE IF NOT EXISTS llm_calls(id INTEGER PRIMARY KEY, ts INTEGER, packet_hash TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, cache_hit INTEGER, response_json TEXT);
CREATE TABLE IF NOT EXISTS gate_checks(id INTEGER PRIMARY KEY, ts INTEGER, scope TEXT, gate TEXT, passed INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER);
""",
}


def db_path() -> Path:
    return data_dir() / "thunder.db"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = str(path or db_path())
    con = sqlite3.connect(p, timeout=30, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    if p != ":memory:":
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    migrate(con)
    return con


def migrate(con: sqlite3.Connection) -> None:
    con.executescript(MIGRATIONS[1])
    row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
    cur = row[0] or 0
    for v in sorted(MIGRATIONS):
        if v > cur:
            if v > 1:
                con.executescript(MIGRATIONS[v])
            con.execute("INSERT INTO schema_version(version) VALUES (?)", (v,))


def integrity_ok(con: sqlite3.Connection) -> bool:
    try:
        return con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


@contextmanager
def tx(con: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    con.execute("BEGIN")
    try:
        yield con
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def now_ms() -> int:
    return int(time.time() * 1000)


def kv_get(con: sqlite3.Connection, key: str, default: Any = None) -> Any:
    r = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def kv_set(con: sqlite3.Connection, key: str, value: Any) -> None:
    con.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, default=str)))


def log_event(con: sqlite3.Connection, level: str, source: str, message: str) -> None:
    from .secrets import scrub
    con.execute("INSERT INTO events(ts,level,source,message) VALUES(?,?,?,?)",
                (now_ms(), level, source, scrub(message)))


def beat(con: sqlite3.Connection, name: str, detail: str = "") -> None:
    con.execute("INSERT INTO heartbeat(name,ts,detail) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET ts=excluded.ts, detail=excluded.detail",
                (name, now_ms(), detail))


def backup(dest_dir: Path | None = None) -> Path:
    src = db_path()
    dest_dir = dest_dir or (data_dir() / "backups")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"thunder-{time.strftime('%Y%m%d-%H%M%S')}.db"
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dest))
    with d:
        s.backup(d)
    s.close(); d.close()
    backups = sorted(dest_dir.glob("thunder-*.db"))
    for old in backups[:-14]:
        old.unlink(missing_ok=True)
    return dest


def disk_usage_mb() -> float:
    total = 0
    for f in data_dir().rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total / 1e6


__all__ = ["connect", "tx", "now_ms", "kv_get", "kv_set", "log_event", "beat", "backup",
           "integrity_ok", "disk_usage_mb", "shutil"]
