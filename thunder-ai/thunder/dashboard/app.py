"""THUNDER dashboard entry point:  streamlit run thunder/dashboard/app.py

Binds to 127.0.0.1 by default (see .streamlit/config.toml). It never runs trading
logic; it reads aggregated tables and writes commands for the engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="THUNDER AI", page_icon="⚡", layout="wide", initial_sidebar_state="auto")

from thunder.dashboard.components import page_setup  # noqa: E402

page_setup("THUNDER")
P = Path(__file__).parent / "pages"
pages = [
    st.Page(P / "home.py", title="Home", icon="🏠", default=True),
    st.Page(P / "arena.py", title="Arena", icon="🏟️"),
    st.Page(P / "strategy.py", title="Strategy detail", icon="📋"),
    st.Page(P / "council.py", title="Council", icon="🧑‍⚖️"),
    st.Page(P / "trades.py", title="Trades", icon="📒"),
    st.Page(P / "risk.py", title="Risk & Recovery", icon="🛡️"),
    st.Page(P / "insights.py", title="Insights", icon="💡"),
    st.Page(P / "backtest_lab.py", title="Backtest Lab", icon="🧪"),
    st.Page(P / "live.py", title="Live (locked)", icon="🔒"),
    st.Page(P / "settings.py", title="Settings", icon="⚙️"),
    st.Page(P / "health.py", title="Health", icon="🩺"),
    st.Page(P / "help.py", title="Help", icon="❓"),
]
st.navigation(pages).run()
