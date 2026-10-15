"""Shared dashboard pieces. The dashboard only READS aggregated tables and WRITES commands."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from ...config import load_config
from ...db import connect, kv_get, now_ms
from ...engine import commands as C
from .. import formatters as fmt

CSS = (Path(__file__).resolve().parents[1] / "theme.css").read_text(encoding="utf-8")

GLOSSARY = {
    "Expectancy": "Average profit per trade after ALL costs (fees, GST, slippage, funding). The single most important number.",
    "R": "One R = the amount you planned to lose if the stop is hit. +0.2R per trade means +₹3 per trade on a ₹15 risk.",
    "Net": "After all costs. 'Gross' is before costs.",
    "Drawdown": "How far equity has fallen from its highest point. Deposits and withdrawals are excluded.",
    "Profit factor": "Total money won ÷ total money lost. Above 1 means more won than lost; we want 1.2+ out-of-sample.",
    "Out-of-sample": "Data the strategy was NOT tuned on. Only these results count as evidence.",
    "Confidence interval": "The range the true average probably lies in (95%). If it includes zero, the edge is not proven.",
    "cost_R": "Fees + slippage as a share of the planned loss. 0.25 means costs eat a quarter of your risk on every trade.",
    "Kill-switch": "If equity falls 10% below its peak, all new trading stops until a human resets it.",
    "Daily loss stop": "If today's realised loss reaches 2% of the day's starting equity, no new trades until tomorrow (IST).",
    "Regime": "The market's current character: trending up/down, sideways range, quiet squeeze, very volatile, or choppy.",
    "Paper": "Simulated trading on live (or sample) data with virtual money. No real orders.",
    "Funding": "A periodic payment between long and short holders of perpetual futures, every 8 hours.",
    "Win rate": "Share of trades that made money after costs. On its own it says little.",
}


def page_setup(title: str, icon: str = "⚡") -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


@st.cache_resource
def _con():
    return connect()


def con():
    return _con()


def cfg():
    return load_config()


def q(sql: str, args: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, con(), params=args)


def kv(key: str, default=None):
    return kv_get(con(), key, default)


def is_sample() -> bool:
    meta = kv("arena_meta", {}) or {}
    return cfg().data_mode == "demo" or bool(meta.get("sample_data"))


def ribbon(mode: str) -> None:
    """Permanent mode ribbon: SAMPLE DATA (grey) / BACKTEST (blue) / PAPER (amber) / LIVE (red, REAL MONEY)."""
    chips = []
    if is_sample():
        chips.append("<span class='th-chip th-sample'>SAMPLE DATA</span>")
    label = {"backtest": "BACKTEST", "paper": "PAPER", "live": "LIVE · REAL MONEY"}.get(mode, mode.upper())
    chips.append(f"<span class='th-chip th-{mode}'>{label}</span>")
    st.markdown(f"<div class='th-ribbon'>{''.join(chips)}</div>", unsafe_allow_html=True)


def engine_status() -> dict:
    r = con().execute("SELECT ts, detail FROM heartbeat WHERE name='engine'").fetchone()
    if not r:
        return {"alive": False, "ts": None}
    d = json.loads(r[1] or "{}")
    d["ts"] = r[0]
    d["alive"] = now_ms() - r[0] < 90_000
    return d


def send(command: str, **args) -> None:
    cid = C.submit(con(), command, **args)
    st.session_state.setdefault("pending_cmds", []).append(cid)
    st.toast(f"{command.replace('_', ' ').title()} sent — waiting for the engine…")


def command_feedback() -> None:
    left = []
    for cid in st.session_state.get("pending_cmds", []):
        s = C.status(con(), cid)
        if s.get("status") == "done":
            st.toast(f"✓ {s['command'].replace('_', ' ').title()}: {s.get('result', '')}")
        elif s.get("status") == "failed":
            st.toast(f"✗ {s['command'].replace('_', ' ').title()} failed — {s.get('result', '')}")
        else:
            left.append(cid)
    st.session_state["pending_cmds"] = left
    if left and not engine_status().get("alive"):
        st.warning("The engine process is not running, so commands are waiting. Start THUNDER with the launcher.")


def empty(msg: str) -> None:
    st.info(msg, icon="ℹ️")


def verdict_banner(summary: dict | None) -> None:
    from ...backtest.promotion import NO_EDGE_MESSAGE, RESEARCH
    if not summary:
        st.markdown("<div class='th-verdict'><b>No research results yet.</b> Run the arena from the Arena page "
                    "(it takes a few minutes).</div>", unsafe_allow_html=True)
        return
    best = [s for s in summary.values() if s["status"] != RESEARCH]
    if not best:
        st.markdown(f"<div class='th-verdict'><b>{NO_EDGE_MESSAGE}</b></div>", unsafe_allow_html=True)
    else:
        names = ", ".join(f"{s['strategy_id']} {s['name']} ({s['status']})" for s in best)
        st.markdown(f"<div class='th-verdict'><b>Strategies past the first gate:</b> {names}. "
                    "This is research evidence, not a promise of future profit.</div>", unsafe_allow_html=True)
    if is_sample():
        st.caption("These results come from SAMPLE (synthetic) data and say nothing about real markets.")


def metric(col, label: str, value: str, delta: str | None = None, help_key: str | None = None, delta_color: str = "normal"):
    col.metric(label, value, delta=delta, help=GLOSSARY.get(help_key or label), delta_color=delta_color)


def plotly_layout(fig, height: int = 340):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=30, b=8), legend=dict(orientation="h", y=-0.2),
                      template="plotly_white" if st.get_option("theme.base") != "dark" else "plotly_dark")
    return fig


def accounts() -> pd.DataFrame:
    df = q("SELECT account_id, strategy_id, instrument, starting_equity, state_json, updated_at FROM accounts WHERE mode='paper'")
    if df.empty:
        return df
    st_ = df["state_json"].map(json.loads)
    df["equity"] = st_.map(lambda s: s["account"]["equity"])
    df["peak"] = st_.map(lambda s: s["account"]["peak"])
    df["halted"] = st_.map(lambda s: s["account"]["halted"])
    df["halt_reason"] = st_.map(lambda s: s["account"]["halt_reason"])
    df["net_cash_flows"] = st_.map(lambda s: s["account"]["net_cash_flows"])
    df["open"] = st_.map(lambda s: s["pos"] is not None)
    df["pending_deposit"] = st_.map(lambda s: s["account"].get("pending_deposit", 0))
    df["day_realised"] = st_.map(lambda s: s["account"]["day_realised"])
    df["day_start_equity"] = st_.map(lambda s: s["account"]["day_start_equity"])
    df["consecutive_losses"] = st_.map(lambda s: s["account"]["consecutive_losses"])
    df["position"] = st_.map(lambda s: s["pos"])
    return df.drop(columns=["state_json"])


def wait_rerun(seconds: float = 0.0) -> None:
    if seconds:
        time.sleep(seconds)
    st.rerun()


__all__ = ["fmt"]
