import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from thunder import cards, strategies
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt

ui.page_setup("Strategy")
st.title("📋 Strategy detail")
ui.command_feedback()
summary = ui.kv("arena_summary", {}) or {}
ids = strategies.TRADING_IDS
sid = st.selectbox("Strategy", ids, format_func=lambda k: f"{k} {strategies.REGISTRY[k].name}")
cls = strategies.REGISTRY[sid]
s = summary.get(sid, {})
mode = st.radio("Results to show", ["backtest", "paper"], horizontal=True,
                format_func=lambda m: {"backtest": "Backtest (out-of-sample)", "paper": "Paper (forward)"}[m])
ui.ribbon(mode)

st.markdown(f"**{cls.name}.** {cls.description_plain}")
st.caption(f"Works in: {', '.join(cls.regimes_allowed) or 'any market type'} · entry by "
           f"{'resting limit order (maker fee)' if cls.entry_method == 'limit' else 'market order at the next candle'}")
if s:
    st.markdown(f"**Status: {s['status']}** — {s['plain']}")

# ---- checklist: confirmed vs tentative ---------------------------------------------
st.subheader("What to look for")
ins = ui.q("SELECT buckets_json FROM insights WHERE scope=? ORDER BY id DESC LIMIT 1", (mode,))
confirmed, watching = [], []
if not ins.empty:
    rows = json.loads(ins.iloc[0, 0]).get("rows", [])
    for r in rows:
        if r.get("strategy_id") == sid and r["n"] >= 10 and r["mean_r"] > 0:
            (confirmed if r["flag"] == "CONFIRMED" else watching).append(r)
for item in cls(**(s.get("params") or {})).checklist_plain():
    st.markdown(f"- ✓ {item}")
for r in confirmed[:5]:
    st.markdown(f"- ✓ **Confirmed:** better when {r['bucket'].replace('_', ' ')} = {r['value']} "
                f"({fmt.r_mult(r['mean_r'])}, n={r['n']})")
for r in watching[:5]:
    st.markdown(f"- ◔ Worth watching (not confirmed): {r['bucket'].replace('_', ' ')} = {r['value']} "
                f"({fmt.r_mult(r['mean_r'])}, n={r['n']}, {r['flag']})")

with st.expander("Parameters (chosen on training data only)"):
    params = s.get("params") or cls.defaults
    st.dataframe(pd.DataFrame({"parameter": list(params), "value": [str(v) for v in params.values()]}),
                 hide_index=True, width="stretch")
    st.caption(f"Parameter combinations tried (trial count): {cls.trial_count()} — pre-registered in code.")

if s:
    with st.expander("Promotion gates (✓ / ✗)"):
        for g in s["gates"]:
            st.markdown(f"{'✅' if g['passed'] else '❌'} **{g['name']}** — {g['detail']}")

# ---- trades -------------------------------------------------------------------------
tr = ui.q("SELECT * FROM trades WHERE mode=? AND strategy_id=? ORDER BY exit_time", (mode, sid))
if tr.empty:
    ui.empty("No trades for this strategy yet in this mode.")
else:
    k = st.columns(4)
    ui.metric(k[0], "Trades", str(len(tr)))
    ui.metric(k[1], "Net expectancy", fmt.r_mult(tr.r_multiple.mean()), help_key="Expectancy")
    ui.metric(k[2], "Win rate", fmt.pct((tr.net_pnl > 0).mean(), 0, sign=False), help_key="Win rate")
    ui.metric(k[3], "Avg cost", fmt.r_mult(((tr.gross_pnl - tr.net_pnl) / tr.realised_risk).mean()), help_key="cost_R")

    cum = tr.r_multiple.cumsum()
    fig = go.Figure(go.Scatter(x=pd.to_datetime(tr.exit_time, unit="ms"), y=cum, mode="lines", name="cumulative R"))
    fig.add_trace(go.Scatter(x=pd.to_datetime(tr.exit_time, unit="ms"), y=cum - cum.cummax(), mode="lines",
                             name="drawdown (R)", line=dict(dash="dot")))
    st.plotly_chart(ui.plotly_layout(fig, 300), width="stretch")
    a, b = st.columns(2)
    a.plotly_chart(ui.plotly_layout(go.Figure(go.Histogram(x=tr.r_multiple, nbinsx=30, name="R")).update_layout(
        title="R-multiple per trade"), 280), width="stretch")
    ex = tr.exit_reason.value_counts()
    b.plotly_chart(ui.plotly_layout(go.Figure(go.Pie(labels=ex.index, values=ex.values, hole=.5)).update_layout(
        title="How trades ended"), 280), width="stretch")
    feats = tr.features_json.map(lambda x: json.loads(x or "{}"))
    tr["hour"] = feats.map(lambda f: f.get("hour_ist"))
    tr["wd"] = feats.map(lambda f: f.get("weekday"))
    hm = tr.dropna(subset=["hour", "wd"]).pivot_table(index="wd", columns="hour", values="r_multiple", aggfunc="mean")
    if not hm.empty:
        hm.index = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(i)] for i in hm.index]
        st.plotly_chart(ui.plotly_layout(go.Figure(go.Heatmap(z=hm.values, x=[f"{int(c):02d}h" for c in hm.columns], y=hm.index,
                        colorscale="RdBu", zmid=0, colorbar=dict(title="R"))).update_layout(title="Average R by IST hour × weekday"), 300),
                        width="stretch")
    rg = tr.groupby("regime").r_multiple.agg(["mean", "count"]).reset_index()
    st.plotly_chart(ui.plotly_layout(go.Figure(go.Bar(x=rg["regime"], y=rg["mean"], text=rg["count"].map(lambda n: f"n={n}"))).update_layout(
        title="Average R by market regime at entry"), 280), width="stretch")
    # waterfall gross -> net -> est. tax
    cfg = ui.cfg()
    gross, fe, fx, gst, sl, fu = (tr[c].sum() for c in ("gross_pnl", "fee_entry", "fee_exit", "gst", "slippage", "funding"))
    net = tr.net_pnl.sum()
    tax = cfg.costs.tax_rate * max(0.0, tr[tr.net_pnl > 0].net_pnl.sum())
    wf = go.Figure(go.Waterfall(x=["Gross", "Fees", "GST", "Slippage", "Funding", "Net", "Est. tax*"],
                                measure=["absolute", "relative", "relative", "relative", "relative", "total", "relative"],
                                y=[gross, -(fe + fx), -gst, -sl, -fu, 0, -tax]))
    st.plotly_chart(ui.plotly_layout(wf.update_layout(title="Where the money went"), 300), width="stretch")
    st.caption("*Tax is an ESTIMATE (30% on net positive gains, no loss set-off) — confirm with a chartered accountant. "
               "Not tax advice.")
    show = tr[["entry_time", "instrument", "side", "entry", "exit", "qty", "exit_reason", "net_pnl", "r_multiple"]].copy()
    show["entry_time"] = show.entry_time.map(lambda t: fmt.ist(t, "%d %b %H:%M"))
    show["net_pnl"] = show.net_pnl.map(lambda x: fmt.inr(x, sign=True))
    show["r_multiple"] = show.r_multiple.map(fmt.r_mult)
    st.dataframe(show.iloc[::-1], hide_index=True, width="stretch", height=260)
    pick = st.selectbox("Show a trade on the chart", tr.index[::-1],
                        format_func=lambda i: f"{fmt.ist(tr.loc[i, 'entry_time'], '%d %b %H:%M')} {tr.loc[i, 'side']} {fmt.r_mult(tr.loc[i, 'r_multiple'])}")
    t = tr.loc[pick]
    cd = ui.q("SELECT open_time_utc AS open_time, open, high, low, close FROM candles WHERE instrument=? AND timeframe='5m' "
              "AND open_time_utc BETWEEN ? AND ? ORDER BY open_time_utc",
              (t.instrument, int(t.entry_time - 60 * 300_000), int(t.exit_time + 30 * 300_000)))
    if not cd.empty:
        x = pd.to_datetime(cd.open_time, unit="ms")
        fig = go.Figure(go.Candlestick(x=x, open=cd.open, high=cd.high, low=cd.low, close=cd.close, name="price"))
        for y, nm, dash in ((t.entry, "entry", "solid"), (t.stop, "stop", "dash"), (t.target, "target", "dot")):
            fig.add_hline(y=y, line_dash=dash, annotation_text=nm)
        fig.add_vline(x=pd.to_datetime(t.entry_time, unit="ms"), line_dash="dot")
        fig.update_layout(xaxis_rangeslider_visible=False)
        st.plotly_chart(ui.plotly_layout(fig, 360), width="stretch")
    with st.expander("Decision trace (why this trade was taken)"):
        st.json(json.loads(t.trace_json or "{}"))

# ---- strategy card ------------------------------------------------------------------
st.subheader("Strategy Card")
if st.button("Export Strategy Card", width="stretch", disabled=not s):
    ui.send("EXPORT_STRATEGY", strategy_id=sid)
for c in [c for c in cards.load_all(ui.con()) if c.strategy_id == sid][:3]:
    st.markdown(f"Card `{c.card_id}` · {c.status} · {fmt.ist(c.created_at)}" + (" · SAMPLE DATA" if c.sample_data else ""))
    d1, d2 = st.columns(2)
    d1.download_button("Download JSON", cards.export_json(c), f"{sid}-{c.card_id}.json", "application/json",
                       width="stretch", key=f"j{c.card_id}")
    d2.download_button("Printable page", cards.printable_html(c), f"{sid}-{c.card_id}.html", "text/html",
                       width="stretch", key=f"h{c.card_id}")
_ = np
