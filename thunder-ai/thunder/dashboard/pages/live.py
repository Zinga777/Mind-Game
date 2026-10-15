import streamlit as st

from thunder import cards
from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.db import kv_get, kv_set
from thunder.execution.live import CONFIRM_PHRASE, connection_test, gate_status, live_enabled
from thunder.secrets import get_secret, mask, register_secret, set_secret

ui.page_setup("Live")
ui.ribbon("live")
st.title("🔒 Live trading")
st.markdown("<div class='th-card' style='border-left:6px solid var(--th-live)'><b>REAL MONEY.</b> Live trading is "
            "locked until every gate below passes. Backtest and paper results do not guarantee future profit, and "
            "real trading can lose the whole allocated amount. The bot never moves money in or out of your wallet.</div>",
            unsafe_allow_html=True)
st.caption("Live code is UNVERIFIED_AGAINST_LIVE_EXCHANGE: it was built and tested against a mock exchange because "
           "CoinDCX could not be reached from the build machine.")
con, cfg = ui.con(), ui.cfg()
all_cards = cards.load_all(con)
card_id = kv_get(con, "live_card_id", None)
card = next((c for c in all_cards if c.card_id == card_id), None)

if kv_get(con, "live_armed", False):
    if st.button("⛔ EXIT ALL & HALT", type="primary", width="stretch"):
        ui.send("EXIT_ALL_HALT")

st.subheader("Gate checklist")
gates = gate_status(con, cfg, card)
for g in gates:
    st.markdown(f"{'✅' if g.passed else '❌'} **{g.name}**  \n<small>{g.plain}</small>", unsafe_allow_html=True)

st.subheader("1 · Choose a Strategy Card")
eligible = [c for c in all_cards if c.status in ("PAPER_PROVEN", "LIVE_ELIGIBLE") and not c.sample_data]
if not eligible:
    ui.empty("No card is PAPER_PROVEN yet. That is expected early on: a strategy must pass the backtest gates AND 30+ days "
             "of forward paper trading first. Keeping real money out is the correct outcome.")
else:
    pick = st.selectbox("Card", eligible, format_func=lambda c: f"{c.strategy_id} {c.name} · {c.status} · {c.card_id}")
    ev = pick.evidence
    st.write(f"Out-of-sample: {ev.get('oos_trades')} trades, {fmt.r_mult(ev.get('expectancy_r'))} per trade after costs. "
             f"Validated capital range: {pick.validated_capital_range}.")
    if st.button("Use this card", width="stretch"):
        kv_set(con, "live_card_id", pick.card_id); st.rerun()

st.subheader("2 · Capital & risk caps")
st.write(f"Allocated capital cap: **{fmt.inr(cfg.capital.allocated_live_cap_inr)}** · risk per trade "
         f"**{fmt.pct(cfg.risk.risk_pct, 2, sign=False)}** (change in Settings). The bot sizes every trade from the real "
         "exchange balance and never above the cap.")

st.subheader("3 · CoinDCX API key")
st.caption("Create a key with TRADE permission only — never withdrawal — and bind it to this computer's IP if possible. "
           "It is stored in your OS keyring (or an owner-only file) and never in logs, the database or exports.")
cur = get_secret("coindcx_api_key")
st.write(f"Stored key: `{mask(cur)}`")
with st.form("key"):
    k = st.text_input("API key", type="password")
    s = st.text_input("API secret", type="password")
    if st.form_submit_button("Save key", width="stretch") and k and s:
        register_secret(k); register_secret(s)
        set_secret("coindcx_api_key", k); set_secret("coindcx_api_secret", s)
        st.success("Saved.")
if st.button("Run read-only connection test", width="stretch", disabled=not cur):
    from thunder.exchanges.coindcx import CoinDCXPrivate
    res = connection_test(con, CoinDCXPrivate(get_secret("coindcx_api_key"), get_secret("coindcx_api_secret"),
                                              api_base=cfg.exchange.api_base, margin_currency=cfg.exchange.margin_currency))
    (st.success if res["ok"] else st.error)(str({k: v for k, v in res.items() if k != "ts"}))

st.subheader("4 · Confirm")
with st.form("phrase"):
    p = st.text_input(f'Type exactly: "{CONFIRM_PHRASE}"')
    if st.form_submit_button("Confirm", width="stretch"):
        ok = p.strip() == CONFIRM_PHRASE
        kv_set(con, "live_phrase_ok", ok)
        (st.success if ok else st.error)("Confirmed." if ok else "Phrase does not match.")

st.subheader("5 · Arm")
st.caption("The smoke test must be run once from a terminal: python scripts/live_smoke_test.py")
all_ok = all(g.passed for g in gates)
if st.button("ARM LIVE TRADING", type="primary", width="stretch", disabled=not all_ok):
    if all(x.passed for x in gate_status(con, cfg, card)):
        kv_set(con, "live_armed", True)
        st.warning("Live trading armed. The first 20 live trades each need your approval below.")
pend = kv_get(con, "live_pending_approval", None)
if pend:
    st.warning(f"Approval needed: {pend['side']} {pend['qty']} {pend['pair']} · stop {pend['stop']} · target {pend['target']}")
    a, b = st.columns(2)
    if a.button("Approve", width="stretch"):
        kv_set(con, "live_approval_decision", {"decision_id": pend["decision_id"], "approved": True})
    if b.button("Reject", width="stretch"):
        kv_set(con, "live_approval_decision", {"decision_id": pend["decision_id"], "approved": False})
st.caption(f"Live currently {'ENABLED' if live_enabled(con, cfg, card) else 'locked'}.")
