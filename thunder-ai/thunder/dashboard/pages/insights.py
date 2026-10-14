import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.insights.report import to_html

ui.page_setup("Insights")
st.title("💡 Insights")
mode = st.radio("Results", ["backtest", "paper"], horizontal=True)
ui.ribbon(mode)
ui.command_feedback()
if st.button("Refresh insights now", width="stretch"):
    ui.send("RUN_INSIGHTS", mode=mode)
row = ui.q("SELECT ts, report_md, buckets_json FROM insights WHERE scope=? ORDER BY id DESC LIMIT 1", (mode,))
if row.empty:
    ui.empty("Nothing to show yet: the first report appears after the arena runs (backtest) or after some paper trades.")
    st.stop()
st.caption(f"Report from {fmt.ist(int(row.ts[0]))}")
md = row.report_md[0]
st.markdown(md)
d1, d2 = st.columns(2)
d1.download_button("Download report (HTML)", to_html(md), f"thunder-insights-{mode}.html", "text/html", width="stretch")
d2.download_button("Download report (Markdown)", md, f"thunder-insights-{mode}.md", "text/markdown", width="stretch")
data = json.loads(row.buckets_json[0])
b = pd.DataFrame(data.get("rows", []))
if not b.empty:
    st.subheader("Bucket tables")
    sid = st.selectbox("Strategy", sorted(b.strategy_id.unique()))
    bk = st.selectbox("Bucket", sorted(b.bucket.unique()))
    t = b[(b.strategy_id == sid) & (b.bucket == bk)].sort_values("mean_r", ascending=False)
    st.dataframe(pd.DataFrame({"Value": t.value, "Trades": t.n, "Mean": t.mean_r.map(fmt.r_mult),
                               "95% CI": [f"{fmt.r_mult(a)} … {fmt.r_mult(c)}" for a, c in zip(t.ci_low, t.ci_high)],
                               "Flag": t.flag}), hide_index=True, width="stretch")
    st.caption("TENTATIVE = fewer than 100 trades · OBSERVED = 100+ · CONFIRMED = also held up in a later period.")
tr = ui.q("SELECT strategy_id, mae_r, mfe_r, net_pnl FROM trades WHERE mode=?", (mode,))
if not tr.empty:
    fig = go.Figure()
    for won, nm in ((True, "winners"), (False, "losers")):
        x = tr[(tr.net_pnl > 0) == won]
        fig.add_trace(go.Scatter(x=x.mae_r, y=x.mfe_r, mode="markers", name=nm, marker=dict(symbol="circle" if won else "x")))
    st.plotly_chart(ui.plotly_layout(fig.update_layout(title="How far trades went against (MAE) and for (MFE) you, in R",
                                                       xaxis_title="MAE (R)", yaxis_title="MFE (R)"), 320), width="stretch")
an = pd.DataFrame(data.get("analysts", []))
if not an.empty:
    st.subheader("Analyst scorecard")
    st.dataframe(an, hide_index=True, width="stretch")
sg = ui.q("SELECT id, ts, strategy_id, suggestion, status FROM suggested_changes ORDER BY id DESC LIMIT 30")
st.subheader("Suggested changes (human-reviewed, never auto-applied)")
if sg.empty:
    ui.empty("No suggestions yet.")
for r in sg.itertuples():
    st.markdown(f"- **{r.strategy_id}** · {r.suggestion} _(status: {r.status})_")
