import streamlit as st
from pydantic import ValidationError

from thunder.config import save_config
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.db import now_ms
from thunder.desk.council_llm import estimate_monthly_cost_usd
from thunder.secrets import get_secret, set_secret

ui.page_setup("Settings")
st.title("⚙️ Settings")
ui.command_feedback()
cfg = ui.cfg()
con = ui.con()


def audit_save(new):
    old, nw = cfg.model_dump(), new.model_dump()
    for sec in nw:
        if old.get(sec) != nw.get(sec):
            con.execute("INSERT INTO settings_audit(ts,key,old,new) VALUES(?,?,?,?)", (now_ms(), sec, str(old.get(sec)), str(nw.get(sec))))
    save_config(new)
    st.success("Saved. The engine picks up new settings on its next start (STOP then START).")


st.subheader("Capital")
st.caption("Paper capital per sub-bot. Deposits and withdrawals are recorded as cash flows — never as profit or loss.")
with st.form("funds"):
    c = st.columns(2)
    amt = c[0].number_input("Amount (₹)", min_value=1.0, value=1000.0, step=500.0)
    kind = c[1].radio("Action", ["Add virtual funds", "Withdraw virtual funds"])
    acc = ui.accounts()
    who = st.selectbox("Sub-bot", ["(all)"] + (list(acc.account_id) if not acc.empty else []))
    if st.form_submit_button("Apply", width="stretch"):
        ui.send("ADD_FUNDS", amount=amt if kind.startswith("Add") else -amt, **({} if who == "(all)" else {"account_id": who}))

with st.form("settings"):
    st.subheader("Capital & risk")
    c = st.columns(2)
    start_eq = c[0].number_input("Starting paper equity per sub-bot (₹)", 100.0, 1e8, cfg.capital.starting_paper_equity_inr, 500.0)
    cap = c[1].number_input("Allocated live capital cap (₹)", 100.0, 1e8, cfg.capital.allocated_live_cap_inr, 500.0)
    risk = c[0].number_input("Risk per trade (% of current equity)", 0.05, 2.0, cfg.risk.risk_pct * 100, 0.05,
                             help="Raising this means bigger losses per trade. The rupee amount already grows with equity.")
    maxr = c[1].number_input("Optional hard rupee ceiling per trade (0 = none)", 0.0, 1e7, cfg.risk.max_risk_per_trade_inr or 0.0, 50.0)
    dls = c[0].number_input("Daily loss stop (%)", 0.5, 10.0, cfg.risk.daily_loss_stop_pct * 100, 0.5)
    mdd = c[1].number_input("Drawdown kill-switch (%)", 2.0, 30.0, cfg.risk.max_drawdown_pct * 100, 1.0)
    mop = c[0].number_input("Max open positions per sub-bot", 1, 5, cfg.risk.max_open_positions,
                            help="Above 1 increases risk: several positions can lose at once.")
    pol = c[1].selectbox("Recovery policy", ["A", "B", "C"], index="ABC".index(cfg.risk.recovery_policy),
                         format_func={"A": "A · Fixed risk (recommended)", "B": "B · Capped recovery (only if the Lab allows)",
                                      "C": "C · De-risk after a losing streak"}.get)
    st.subheader("Costs (check against your CoinDCX fee tier)")
    c = st.columns(3)
    mk = c[0].number_input("Maker fee (%)", 0.0, 1.0, cfg.costs.maker_fee * 100, 0.005, format="%.3f")
    tk = c[1].number_input("Taker fee (%)", 0.0, 1.0, cfg.costs.taker_fee * 100, 0.005, format="%.3f")
    gst = c[2].number_input("GST on fees (%)", 0.0, 50.0, cfg.costs.gst * 100, 1.0)
    sm = c[0].number_input("Market slippage (bps)", 0.0, 100.0, cfg.costs.slip_market_bps, 0.5)
    ss = c[1].number_input("Stop slippage (bps)", 0.0, 100.0, cfg.costs.slip_stop_bps, 0.5)
    fr = c[2].number_input("Funding rate per 8h when unknown (%)", -1.0, 1.0, cfg.costs.funding_rate_per_interval * 100, 0.005, format="%.3f")
    tax = st.number_input("Tax estimate on net gains (%)", 0.0, 60.0, cfg.costs.tax_rate * 100, 1.0,
                          help="An estimate only. Confirm the treatment of crypto futures with a chartered accountant.")
    st.subheader("Market")
    inst = st.text_input("Instruments (comma separated)", ", ".join(cfg.exchange.instruments))
    q2i = st.number_input("INR per USDT used for INR-margined futures", 1.0, 500.0, cfg.exchange.usdt_inr_rate, 0.5,
                          help="UNVERIFIED default; check the rate CoinDCX applies to INR-margin futures.")
    st.subheader("Council")
    mode = st.selectbox("Council mode", ["rules_only", "rules_plus_llm"], index=["rules_only", "rules_plus_llm"].index(cfg.council.mode))
    calls = st.number_input("Max LLM calls per day", 0, 1000, cfg.council.max_llm_calls_per_day)
    usd = st.number_input("Max LLM spend per day (USD)", 0.0, 100.0, cfg.council.max_llm_cost_usd_per_day, 0.5)
    st.caption(f"Estimated monthly LLM cost at that call limit: about ${estimate_monthly_cost_usd(calls, cfg.council.llm_model):.2f} "
               f"(model {cfg.council.llm_model}). The app works fully without a key.")
    st.subheader("Notifications (off by default)")
    tg = st.checkbox("Telegram alerts", cfg.alerts.telegram_enabled)
    em = st.checkbox("Email alerts", cfg.alerts.email_enabled)
    confirm = st.text_input("Type CHANGE to save risk-raising changes", help="Required when risk % or drawdown limit goes up.")
    if st.form_submit_button("Save settings", type="primary", width="stretch"):
        try:
            new = cfg.model_copy(deep=True)
            new.capital.starting_paper_equity_inr, new.capital.allocated_live_cap_inr = start_eq, cap
            new.risk.risk_pct, new.risk.max_risk_per_trade_inr = risk / 100, (maxr or None)
            new.risk.daily_loss_stop_pct, new.risk.max_drawdown_pct = dls / 100, mdd / 100
            new.risk.max_open_positions, new.risk.recovery_policy = int(mop), pol
            new.costs.maker_fee, new.costs.taker_fee, new.costs.gst = mk / 100, tk / 100, gst / 100
            new.costs.slip_market_bps, new.costs.slip_stop_bps = sm, ss
            new.costs.funding_rate_per_interval, new.costs.tax_rate = fr / 100, tax / 100
            new.exchange.instruments = [x.strip() for x in inst.split(",") if x.strip()]
            new.exchange.usdt_inr_rate = q2i
            new.council.mode, new.council.max_llm_calls_per_day, new.council.max_llm_cost_usd_per_day = mode, int(calls), usd
            new.alerts.telegram_enabled, new.alerts.email_enabled = tg, em
            new = type(cfg).model_validate(new.model_dump())
            raising = (new.risk.risk_pct > cfg.risk.risk_pct or new.risk.max_drawdown_pct > cfg.risk.max_drawdown_pct
                       or new.risk.daily_loss_stop_pct > cfg.risk.daily_loss_stop_pct or new.risk.max_open_positions > cfg.risk.max_open_positions)
            if raising and confirm.strip() != "CHANGE":
                st.error("These changes raise risk. Type CHANGE to confirm.")
            else:
                audit_save(new)
        except ValidationError as e:
            st.error("Some values are not allowed: " + "; ".join(x["msg"] for x in e.errors()))

st.subheader("Optional keys")
with st.form("keys"):
    a = st.text_input("Anthropic API key (only for the LLM council)", type="password")
    t1 = st.text_input("Telegram bot token", type="password")
    t2 = st.text_input("Telegram chat id")
    if st.form_submit_button("Save keys", width="stretch"):
        for name, v in (("anthropic_api_key", a), ("telegram_token", t1), ("telegram_chat_id", t2)):
            if v:
                set_secret(name, v)
        st.success("Saved securely.")
st.caption("Anthropic key: " + ("set" if get_secret("anthropic_api_key") else "not set") + " · Telegram: "
           + ("set" if get_secret("telegram_token") else "not set"))

st.subheader("Data mode")
c = st.columns(2)
if c[0].button("Use demo data", width="stretch", disabled=cfg.data_mode == "demo"):
    ui.send("SET_MODE", data_mode="demo"); ui.send("LOAD_DEMO")
if c[1].button("Use real CoinDCX data", width="stretch", disabled=cfg.data_mode == "real"):
    ui.send("SET_MODE", data_mode="real"); ui.send("DOWNLOAD_DATA")

st.subheader("Danger zone")
with st.form("reset"):
    st.write("Reset paper simulation: deletes all paper trades and restarts every sub-bot at its starting equity. "
             "Backtest results are kept.")
    ph = st.text_input("Type RESET to confirm")
    if st.form_submit_button("Reset paper simulation", width="stretch"):
        if ph.strip() == "RESET":
            ui.send("RESET_PAPER")
        else:
            st.error("Type RESET exactly.")
au = ui.q("SELECT ts, key, new FROM settings_audit ORDER BY id DESC LIMIT 10")
with st.expander("Change log"):
    for r in au.itertuples():
        st.markdown(f"- {fmt.ist(r.ts)} · {r.key}")
