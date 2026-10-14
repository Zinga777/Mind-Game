import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from thunder import strategies
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt

ui.page_setup("Backtest Lab")
ui.ribbon("backtest")
st.title("🧪 Backtest Lab")
st.caption("In-sample (training) and out-of-sample results side by side. Optimisation happens ONLY on training data; "
           "the final test period is touched once per strategy version.")
ui.command_feedback()
cfg = ui.cfg()
job = ui.kv("job_arena", {}) or {}
c = st.columns(2)
c[0].multiselect("Instruments", cfg.exchange.instruments, default=cfg.exchange.instruments, disabled=True,
                 help="Change instruments in Settings.")
if c[1].button("Run full research (all strategies)", type="primary", width="stretch", disabled=job.get("state") == "running"):
    ui.send("RUN_ARENA")
if job.get("state") == "running":
    st.progress(0.5, text=f"Running in the background… {job.get('progress', '')}")
summary = ui.kv("arena_summary", {}) or {}
if not summary:
    ui.empty("No results yet.")
    st.stop()
sid = st.selectbox("Strategy", list(summary), format_func=lambda k: f"{k} {strategies.REGISTRY[k].name}")
runs = ui.q("SELECT instrument, metrics_json, params_json, trial_count, finished_at, sample_data FROM strategy_runs "
            "WHERE strategy_id=? AND mode='backtest' ORDER BY finished_at DESC", (sid,))
if runs.empty:
    st.stop()
import json
latest = runs.groupby("instrument").head(1)
for r in latest.itertuples():
    m = json.loads(r.metrics_json)
    st.subheader(f"{r.instrument}" + (" · SAMPLE DATA" if r.sample_data else ""))
    rows = []
    for split in ("train", "validation", "test", "oos"):
        x = m.get(split) or {}
        rows.append({"Period": {"train": "Training (in-sample)", "validation": "Validation", "test": "Final test",
                                "oos": "All out-of-sample"}[split], "Trades": x.get("trades", 0),
                     "Net expectancy": fmt.r_mult(x.get("expectancy_r")), "Profit factor": round(x.get("profit_factor", 0), 2),
                     "Max DD": fmt.pct(x.get("max_dd_pct"), sign=False), "Avg cost": fmt.r_mult(x.get("avg_cost_r")),
                     "Net ₹ (research capital)": fmt.inr(x.get("net_pnl"))})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"Split dates: " + ", ".join(f"{k} {fmt.ist(v[0], '%d %b %y')}–{fmt.ist(v[1], '%d %b %y')}"
                                             for k, v in (m.get("split_times") or {}).items()))
    k = st.columns(3)
    k[0].metric("Costs ×1.5", fmt.r_mult(m.get("exp_cost15")), help="Expectancy if fees and slippage were 50% higher")
    k[1].metric("Without best 3 trades", fmt.r_mult(m.get("exp_minus_best3")))
    k[2].metric("Neighbouring settings positive", fmt.pct(m.get("neighbour_share"), 0, sign=False))
    wf = m.get("walk_forward") or {}
    st.caption(f"Walk-forward (re-optimised every month on the previous 3 months): {wf.get('trades', 0)} trades, "
               f"{fmt.r_mult(wf.get('expectancy_r'))}. Random-entry comparison: corrected p = {m.get('q_value', 1):.3f}.")
    grid = m.get("grid") or []
    if grid:
        keys = list(strategies.REGISTRY[sid].grid)
        if len(keys) >= 2:
            g = pd.DataFrame([{**p, "r": e, "n": n} for p, e, n in grid])
            pv = g.pivot_table(index=keys[0], columns=keys[1], values="r", aggfunc="mean")
            st.plotly_chart(ui.plotly_layout(go.Figure(go.Heatmap(z=pv.values, x=[str(x) for x in pv.columns],
                            y=[str(y) for y in pv.index], colorscale="RdBu", zmid=0)).update_layout(
                            title=f"Sensitivity on TRAINING data: {keys[0]} × {keys[1]} (expectancy R)"), 280),
                            width="stretch", key=f"hm{r.instrument}")
    cap = m.get("capital_scaling") or []
    if cap:
        st.dataframe(pd.DataFrame([{"Capital": fmt.inr(x["capital"], 0), "Trades": x["trades"],
                                    "Expectancy": fmt.r_mult(x["expectancy_r"]), "Avg cost": fmt.r_mult(x["avg_cost_r"]),
                                    "Rejected as undercapitalised": x["undercapitalised"]} for x in cap]),
                     hide_index=True, width="stretch")
s = summary[sid]
st.subheader("Gates")
for g in s["gates"]:
    st.markdown(f"{'✅' if g['passed'] else '❌'} {g['name']} — {g['detail']}")
st.subheader("Run history")
st.dataframe(pd.DataFrame({"Finished": runs.finished_at.map(fmt.ist), "Instrument": runs.instrument,
                           "Trial count": runs.trial_count, "Sample data": runs.sample_data.astype(bool)}),
             hide_index=True, width="stretch")
