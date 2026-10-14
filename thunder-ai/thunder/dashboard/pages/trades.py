import io
import json

import pandas as pd
import streamlit as st

from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt

ui.page_setup("Trades")
st.title("📒 Trades")
mode = st.radio("Mode", ["paper", "backtest", "live"], horizontal=True)
ui.ribbon(mode)
tr = ui.q("SELECT * FROM trades WHERE mode=? ORDER BY exit_time DESC", (mode,))
if tr.empty:
    ui.empty("No trades in this mode yet.")
    st.stop()
c = st.columns(3)
strat = c[0].multiselect("Strategy", sorted(tr.strategy_id.unique()))
inst = c[1].multiselect("Instrument", sorted(tr.instrument.unique()))
side = c[2].multiselect("Side", ["long", "short"])
if strat:
    tr = tr[tr.strategy_id.isin(strat)]
if inst:
    tr = tr[tr.instrument.isin(inst)]
if side:
    tr = tr[tr.side.isin(side)]
view = pd.DataFrame({
    "Mode": tr["mode"].str.upper(), "Strategy": tr.strategy_id, "Instrument": tr.instrument, "Side": tr.side,
    "Entry (IST)": tr.entry_time.map(lambda t: fmt.ist(t, "%d %b %H:%M")),
    "Exit (IST)": tr.exit_time.map(lambda t: fmt.ist(t, "%d %b %H:%M")),
    "Entry": tr.entry.round(2), "Exit": tr.exit.round(2), "Qty": tr.qty, "Stop": tr.stop.round(2),
    "Target": tr.target.round(2), "Exit reason": tr.exit_reason, "Gross ₹": tr.gross_pnl.round(2),
    "Fees+GST ₹": (tr.fee_entry + tr.fee_exit + tr.gst).round(2), "Slippage ₹": tr.slippage.round(2),
    "Funding ₹": tr.funding.round(2), "Net ₹": tr.net_pnl.round(2), "R": tr.r_multiple.round(2),
})
st.caption(f"{len(view)} trades · net {fmt.inr(tr.net_pnl.sum(), sign=True)} · gross {fmt.inr(tr.gross_pnl.sum(), sign=True)} "
           "(gross and net always shown side by side)")
ev = st.dataframe(view, hide_index=True, width="stretch", height=420, on_select="rerun", selection_mode="single-row")
sel = ev.selection.rows if ev and hasattr(ev, "selection") else []
if sel:
    t = tr.iloc[sel[0]]
    st.subheader("Decision trace")
    st.json({"trace": json.loads(t.trace_json or "{}"), "features at decision": json.loads(t.features_json or "{}")})
a, b = st.columns(2)
a.download_button("Download CSV", view.to_csv(index=False).encode(), f"thunder-{mode}-trades.csv", "text/csv", width="stretch")
buf = io.BytesIO()
try:
    view.to_excel(buf, index=False)
    b.download_button("Download Excel", buf.getvalue(), f"thunder-{mode}-trades.xlsx",
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
except Exception:
    b.caption("Excel export needs the optional 'openpyxl' package; CSV opens in Excel too.")
