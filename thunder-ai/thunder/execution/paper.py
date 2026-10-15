"""Paper execution. Fills are simulated by the SAME StrategyRunner / fill model the
backtest uses (thunder.backtest.runner + thunder.execution.fills); this module only
holds the paper-account bookkeeping helpers so there is no duplicated logic."""
from __future__ import annotations

import json
import sqlite3

from ..db import now_ms
from ..risk.killswitch import AccountState


def add_virtual_funds(con: sqlite3.Connection, account_id: str, amount: float, state: AccountState,
                      deposit_shock_pct: float = 0.25) -> None:
    """Paper deposit (+) or withdrawal (-). Recorded in cash_flows; never counted as P&L."""
    if amount < 0 and -amount > state.equity:
        raise ValueError("cannot withdraw more than the account holds")
    state.apply_cash_flow(amount, now_ms(), deposit_shock_pct, confirmed=True)
    con.execute("INSERT INTO cash_flows(mode,account_id,ts,amount,kind,source,confirmed_by_owner) VALUES(?,?,?,?,?,?,1)",
                ("paper", account_id, now_ms(), amount, "deposit" if amount > 0 else "withdrawal", "owner"))


def load_account(con: sqlite3.Connection, account_id: str) -> dict | None:
    r = con.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    return dict(r) if r else None


def save_account(con: sqlite3.Connection, account_id: str, mode: str, strategy_id: str, instrument: str,
                 params: dict, starting_equity: float, state: dict) -> None:
    con.execute("""INSERT INTO accounts(account_id,mode,strategy_id,instrument,params_json,starting_equity,state_json,updated_at)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET state_json=excluded.state_json,
        params_json=excluded.params_json, updated_at=excluded.updated_at""",
                (account_id, mode, strategy_id, instrument, json.dumps(params), starting_equity,
                 json.dumps(state, default=float), now_ms()))
