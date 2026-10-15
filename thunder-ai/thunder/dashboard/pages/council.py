import json

import plotly.graph_objects as go
import streamlit as st

from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt

ui.page_setup("Council")
st.title("🧑‍⚖️ Council")
st.caption("Every trade idea passes the same desk: specialist analysts, one challenge round, a 100-point scorecard "
           "(a ranking tool, not a probability), hard disqualifications, then the independent risk guard.")
mode = st.radio("Source", ["paper", "backtest"], horizontal=True)
ui.ribbon(mode)
states = ["QUALIFIED", "WAIT", "DISQUALIFIED", "RISK_REJECTED"]
pick = st.multiselect("States", states, default=states)
df = ui.q(f"SELECT * FROM candidates WHERE mode=? AND state IN ({','.join('?' * len(pick))}) ORDER BY candle_close_time DESC LIMIT 300",
          (mode, *pick)) if pick else ui.q("SELECT * FROM candidates WHERE 0")
if df.empty:
    ui.empty("No candidates yet. Sub-bots propose ideas only when their setup appears.")
    st.stop()
reasons = df.reason.str.replace(r"\d+(\.\d+)?", "#", regex=True).value_counts().head(10)
st.plotly_chart(ui.plotly_layout(go.Figure(go.Bar(y=reasons.index[::-1], x=reasons.values[::-1], orientation="h")).update_layout(
    title="Most common reasons ideas were turned down"), 320), width="stretch")
rf = st.selectbox("Filter by reason", ["(all)"] + list(reasons.index))
if rf != "(all)":
    df = df[df.reason.str.replace(r"\d+(\.\d+)?", "#", regex=True) == rf]
chip = {"QUALIFIED": "🟢", "WAIT": "🟡", "DISQUALIFIED": "⚪", "RISK_REJECTED": "🔴"}
for r in df.head(40).itertuples():
    comp = json.loads(r.components_json or "{}")
    rep = json.loads(r.reports_json or "{}")
    with st.expander(f"{chip.get(r.state, '')} {r.state} · {r.strategy_id} {r.direction} {r.instrument} · "
                     f"{fmt.ist(r.candle_close_time, '%d %b %H:%M')} · score {r.score:.0f} — {r.reason}"):
        if comp:
            fig = go.Figure()
            for k, v in comp.items():
                fig.add_trace(go.Bar(y=["score"], x=[v], name=k.replace("_", " "), orientation="h"))
            fig.update_layout(barmode="stack", xaxis=dict(range=[0, 100]))
            st.plotly_chart(ui.plotly_layout(fig, 170), width="stretch", key=f"sc{r.id}")
        for a in rep.get("reports", []):
            st.markdown(f"**{a['analyst']}** — {a['direction']}")
            for e in a.get("evidence", []):
                st.markdown(f"- {e}")
            for c in a.get("contradictions", []):
                st.markdown(f"- ⚠️ {c}")
            if a.get("missing_information"):
                st.caption("Missing: " + ", ".join(a["missing_information"]))
        for n in rep.get("challenge", []):
            st.markdown(f"🗣️ {n}")
        if r.llm_json:
            st.markdown(f"**LLM review:** {json.loads(r.llm_json)}")
        if rep.get("guard"):
            st.caption("Risk guard: " + " → ".join(f"{n} {'✓' if ok else '✗'}" for n, ok in rep["guard"]))
