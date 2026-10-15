import json

import pandas as pd
import streamlit as st

from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.db import db_path, disk_usage_mb, now_ms

ui.page_setup("Health")
st.title("🩺 Health")
es = ui.engine_status()
c = st.columns(3)
c[0].metric("Engine heartbeat", fmt.ago(es.get("ts"), now_ms()))
c[1].metric("Database size", f"{db_path().stat().st_size / 1e6:.1f} MB" if db_path().exists() else "—")
c[2].metric("Data folder", f"{disk_usage_mb():.0f} MB")
hrs = ui.kv("uptime_hours", []) or []
if hrs:
    st.metric("Engine uptime (hours seen / hours since first start)", fmt.pct(len(set(hrs)) / max(1, hrs[-1] - hrs[0] + 1), 0, sign=False))
st.subheader("Data quality")
dq = ui.q("SELECT instrument, ts, report_json FROM data_quality ORDER BY id DESC LIMIT 6")
for r in dq.itertuples():
    d = json.loads(r.report_json)
    st.markdown(f"**{r.instrument}** ({fmt.ist(r.ts)}): {d.get('rows', d.get('stored_5m', '?'))} candles, "
                f"{d.get('gap_count', 0)} gaps, {d.get('duplicates', 0)} duplicates, {len(d.get('outliers', []))} quarantined spikes"
                + (" · SAMPLE DATA" if d.get("sample_data") else ""))
st.subheader("Last fetch per instrument")
hb = ui.q("SELECT name, ts, detail FROM heartbeat ORDER BY name")
st.dataframe(pd.DataFrame({"What": hb.name, "When": hb.ts.map(lambda t: fmt.ago(t, now_ms())), "Detail": hb.detail.str.slice(0, 120)}),
             hide_index=True, width="stretch")
st.subheader("LLM usage today")
llm = ui.q("SELECT COUNT(*) n, COALESCE(SUM(cost_usd),0) usd, COALESCE(SUM(cache_hit),0) hits FROM llm_calls WHERE ts > ?",
           (now_ms() - now_ms() % 86_400_000,))
st.write(f"{int(llm.n[0])} calls ({int(llm.hits[0])} from cache) · about ${llm.usd[0]:.3f}")
st.subheader("Recent errors")
er = ui.q("SELECT ts, source, message FROM events WHERE level IN ('ERROR','HALT','WARN') ORDER BY id DESC LIMIT 15")
if er.empty:
    st.success("No recent errors.")
fixes = {"fetch failed": "Check the internet connection; the bot retries automatically.",
         "Error ID": "Details are in data/logs/engine.log under that Error ID.",
         "stale": "No fresh candles: entries pause until data is fresh again (rule H5)."}
for r in er.itertuples():
    tip = next((v for k, v in fixes.items() if k in r.message), "")
    st.markdown(f"- {fmt.ist(r.ts, '%d %b %H:%M')} · **{r.source}** · {r.message}" + (f"  \n  _Fix: {tip}_" if tip else ""))
