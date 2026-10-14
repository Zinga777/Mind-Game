import streamlit as st

from thunder import strategies
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.db import now_ms
from thunder.features.regime import PLAIN

ui.page_setup("Home")
cfg = ui.cfg()

# ---- first-run setup wizard (3 screens max, no API key asked) ----------------------
if not ui.kv("setup_done", False):
    st.title("⚡ Welcome to THUNDER")
    step = st.session_state.get("wiz", 1)
    if step == 1:
        st.subheader("1 of 3 · What THUNDER does")
        st.write("THUNDER runs many small practice robots (\"sub-bots\"), each trying one trading idea with "
                 "**virtual money**. It measures honestly — after every fee — whether any idea really works, "
                 "and keeps real money out until one has proven itself. *No validated strategy* is a normal, useful answer.")
        if st.button("Next", type="primary", width="stretch"):
            st.session_state["wiz"] = 2; st.rerun()
    elif step == 2:
        st.subheader("2 of 3 · Which data?")
        choice = st.radio("Start with", ["Demo data (works offline, clearly marked SAMPLE DATA)",
                                         "Real CoinDCX data (needs internet; downloads ~12 months)"])
        st.write("Either way, everything is **paper trading** (no real orders). Live trading stays locked.")
        if st.button("Next", type="primary", width="stretch"):
            st.session_state["wiz_mode"] = "real" if choice.startswith("Real") else "demo"
            st.session_state["wiz"] = 3; st.rerun()
    else:
        from thunder.config.loader import data_dir
        st.subheader("3 of 3 · Where your files live")
        st.code(str(data_dir()), language=None)
        st.write("Back up this folder to keep your history. API keys are never stored here in plain text "
                 "when your computer has a secure keyring.")
        if st.button("Finish and start paper trading", type="primary", width="stretch"):
            mode = st.session_state.get("wiz_mode", "demo")
            ui.send("SET_MODE", data_mode=mode)
            if mode == "real":
                ui.send("DOWNLOAD_DATA")
            ui.send("START")
            from thunder.db import kv_set
            kv_set(ui.con(), "setup_done", True)
            st.rerun()
    st.stop()

ui.ribbon("paper")
st.title("⚡ THUNDER")


@st.fragment(run_every=5)
def status_strip():
    ui.command_feedback()
    es = ui.engine_status()
    now = now_ms()
    last = max([v for v in (es.get("last") or {}).values() if v] or [0])
    data_now = es.get("now") or now
    running = es.get("running") and es.get("alive")
    c = st.columns(4)
    c[0].markdown(f"**Engine** {'🟢 Running' if running else ('⏸️ Stopped' if es.get('alive') else '⚪ Offline')}")
    fresh = fmt.ago(last + 300_000, data_now) if last else "no data"
    c[1].markdown(f"**Last candle** {fresh}", help="Time since the latest closed 5-minute candle"
                  + (" (demo clock)" if cfg.data_mode == "demo" else ""))
    c[2].markdown(f"**Data** {'SAMPLE' if cfg.data_mode == 'demo' else 'CoinDCX'}")
    accts = ui.accounts()
    halted = int(accts["halted"].sum()) if not accts.empty else 0
    c[3].markdown(f"**Kill-switch** {'🛑 ' + str(halted) + ' halted' if halted else '✅ none tripped'}")
    if es.get("stopped_safely"):
        st.error(f"The engine stopped safely: {es['stopped_safely']}")
    b1, b2 = st.columns(2)
    if b1.button("▶ START", type="primary", width="stretch", disabled=bool(running)):
        ui.send("START")
    if b2.button("■ STOP", width="stretch", disabled=not running):
        ui.send("STOP")

    # KPIs (paper, all sub-bots combined)
    if accts.empty:
        ui.empty("Nothing to show yet: press START. In demo mode the first paper trades appear within minutes; "
                 "with real data the bot needs about 2 days before the first report.")
        return
    eq = accts["equity"].sum()
    start = accts["starting_equity"].sum() + accts["net_cash_flows"].sum()
    tr = ui.q("SELECT exit_time, net_pnl FROM trades WHERE mode='paper'")
    day0 = data_now - 86_400_000
    wk0 = data_now - 7 * 86_400_000
    today = tr[tr.exit_time >= day0].net_pnl.sum() if not tr.empty else 0.0
    week = tr[tr.exit_time >= wk0].net_pnl.sum() if not tr.empty else 0.0
    k = st.columns(3)
    ui.metric(k[0], "Equity (all sub-bots)", fmt.inr(eq), help_key="Paper")
    ui.metric(k[1], "Net result, all time", fmt.inr(eq - start, sign=True), help_key="Net")
    ui.metric(k[2], "Net today / 7 days", f"{fmt.inr(today, sign=True)} / {fmt.inr(week, sign=True)}", help_key="Net")
    k2 = st.columns(3)
    ui.metric(k2[0], "Open positions", str(int(accts["open"].sum())))
    ui.metric(k2[1], "Trades today", str(int((tr.exit_time >= day0).sum()) if not tr.empty else 0))
    dd = (1 - accts["equity"] / accts["peak"]).max()
    ui.metric(k2[2], "Worst drawdown", fmt.pct(dd, sign=False), help_key="Drawdown")
    used = (-accts["day_realised"] / (cfg.risk.daily_loss_stop_pct * accts["day_start_equity"])).clip(lower=0).max()
    st.progress(float(min(1.0, used)), text=f"Daily-loss budget used by the worst sub-bot: {fmt.pct(used, 0, sign=False)}")


status_strip()

st.subheader("Verdict")
ui.verdict_banner(ui.kv("arena_summary"))

st.subheader("What the bot is waiting for right now")
mn = ui.kv("market_now", {}) or {}
if not mn:
    ui.empty("Waiting for the first candles to be processed.")
for pair, m in mn.items():
    reg = m["regime"]
    idle = [s.id for s in (strategies.REGISTRY[k] for k in strategies.TRADING_IDS) if s.regimes_allowed and reg not in s.regimes_allowed]
    active = [k for k in strategies.TRADING_IDS if k not in idle]
    st.markdown(f"**{pair}** — market is {PLAIN.get(reg, reg)} (`{reg}`).  \n"
                f"Watching for setups: {', '.join(active) or 'none'}.  \n"
                f"Idle (wrong market type): {', '.join(idle) or 'none'}.")

st.subheader("Latest events")
ev = ui.q("SELECT ts, level, source, message FROM events ORDER BY id DESC LIMIT 5")
if ev.empty:
    ui.empty("No events yet.")
for r in ev.itertuples():
    icon = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❗", "HALT": "🛑"}.get(r.level, "•")
    st.markdown(f"{icon} {fmt.ist(r.ts, '%d %b %H:%M')} · {r.message}", help=fmt.utc(r.ts))
