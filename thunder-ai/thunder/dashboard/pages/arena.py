import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from thunder import strategies
from thunder.backtest import promotion
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt

ui.page_setup("Arena")
ui.ribbon("backtest")
st.title("🏟️ Strategy Arena")
st.caption("Ranked by status, then by the cautious (lower) end of the net-expectancy confidence interval, on data the "
           "strategies were NOT tuned on — never by win rate "
           "or gross profit. Edge is measured at research capital; the 'Capital needed' column shows what your "
           "account size can actually trade.")
ui.command_feedback()
summary = ui.kv("arena_summary", {}) or {}
meta = ui.kv("arena_meta", {}) or {}
job = ui.kv("job_arena", {}) or {}

c1, c2 = st.columns([1, 2])
if c1.button("Run / refresh the arena", type="primary", width="stretch", disabled=job.get("state") == "running"):
    ui.send("RUN_ARENA")
if job.get("state") == "running":
    c2.info(f"Arena running… {job.get('progress', '')}")
elif meta:
    c2.caption(f"Last run {fmt.ist(meta.get('finished_at'))} · took {meta.get('seconds', 0):.0f} s"
               + (" · SAMPLE DATA" if meta.get("sample_data") else ""))

ui.verdict_banner(summary or None)
if not summary:
    st.stop()

mn = ui.kv("market_now", {}) or {}
regs = {m["regime"] for m in mn.values()}
paper = ui.q("SELECT strategy_id, COUNT(*) n, AVG(r_multiple) r FROM trades WHERE mode='paper' AND exit_time > "
             "(SELECT COALESCE(MAX(exit_time),0) - 30*86400000 FROM trades WHERE mode='paper') GROUP BY strategy_id")
paper = paper.set_index("strategy_id") if not paper.empty else paper
rows = []
for sid, s in summary.items():
    cls = strategies.REGISTRY[sid]
    fit = "any market" if not cls.regimes_allowed else (
        "fits now" if regs & set(cls.regimes_allowed) else f"idle (needs {', '.join(r.split('_')[0].lower() for r in cls.regimes_allowed)})")
    caps = s.get("capital_scaling", {}).get(s["best_instrument"], [])
    need = next((c["capital"] for c in caps if c["trades"] >= 5), None)
    rows.append({
        "Strategy": f"{sid} {s['name']}", "Status": s["status"] + (" (tentative)" if s.get("tentative") else ""),
        "OOS trades": s["oos_trades"], "Net expectancy": fmt.r_mult(s["expectancy_r"]),
        "95% CI": f"{fmt.r_mult(s['ci'][0])} … {fmt.r_mult(s['ci'][1])}" if s["ci"][0] == s["ci"][0] else "—",
        "Profit factor": round(s["profit_factor"], 2), "Max DD": fmt.pct(s["max_dd"], sign=False),
        "Last 30d paper": (fmt.r_mult(paper.loc[sid, "r"]) + f" ({int(paper.loc[sid, 'n'])})") if not paper.empty and sid in paper.index else "—",
        "Regime fit": fit, "Capital needed": fmt.inr(need, 0) if need else "not feasible ≤ ₹5,00,000",
        # honest ranking: promotion status first, then the LOWER end of the 95% CI of net expectancy,
        # so a lucky handful of trades can never outrank a large, consistent sample
        "_status": promotion.LADDER.index(s["status"]),
        "_ci_low": s["ci"][0] if s["ci"][0] == s["ci"][0] else -9.0,
    })
df = pd.DataFrame(rows).sort_values(["_status", "_ci_low"], ascending=False).drop(columns=["_status", "_ci_low"])
df.insert(0, "Rank", range(1, len(df) + 1))
status_f = st.multiselect("Filter by status", sorted(df["Status"].unique()), placeholder="All statuses")
if status_f:
    df = df[df["Status"].isin(status_f)]
st.dataframe(df, hide_index=True, width="stretch")

bm = ui.kv("arena_benchmarks", {}) or {}
for pair, b in bm.items():
    st.caption(f"Controls on {pair}: random entry (C1) averaged {fmt.r_mult(b['c1_expectancy_r'])} over {b['c1_trades']} "
               f"trades; buy-and-hold over the test period returned {fmt.pct(b['buy_hold_return'])}.")

st.subheader("Out-of-sample equity curves (research capital)")
curves = ui.kv("arena_curves", {}) or {}
pick = st.multiselect("Show strategies", sorted(curves), default=sorted(curves)[:4])
fig = go.Figure()
for k in pick:
    pts = curves[k]
    if pts:
        fig.add_trace(go.Scatter(x=pd.to_datetime([p[0] for p in pts], unit="ms"), y=[p[1] for p in pts], name=k, mode="lines"))
for pair, b in bm.items():
    for j, cur in enumerate(b.get("c1_curves", [])[:2]):
        fig.add_trace(go.Scatter(x=pd.to_datetime([p[0] for p in cur], unit="ms"), y=[p[1] for p in cur],
                                 name=f"C1 random {pair} #{j + 1}", mode="lines", line=dict(dash="dash", color="grey")))
    bh = b.get("bh_curve") or []
    if bh:
        fig.add_trace(go.Scatter(x=pd.to_datetime([p[0] for p in bh], unit="ms"), y=[p[1] for p in bh],
                                 name=f"C2 buy & hold {pair}", mode="lines", line=dict(dash="dot", color="grey")))
st.plotly_chart(ui.plotly_layout(fig, 380), width="stretch")
st.caption("Validation and test periods are joined; dashed grey lines are the random-entry control, dotted is buy-and-hold. "
           "Backtest results are not an expected return.")
