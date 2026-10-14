import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from thunder.dashboard import components as ui
from thunder.dashboard import formatters as fmt
from thunder.risk.killswitch import HALT_CONFIRM_PHRASE
from thunder.risk.recovery import martingale_ruin_table

ui.page_setup("Risk")
ui.ribbon("paper")
st.title("🛡️ Risk & Recovery")
ui.command_feedback()
cfg = ui.cfg()
acc = ui.accounts()
if acc.empty:
    ui.empty("No paper accounts yet — press START on the Home page.")
else:
    acc["drawdown"] = 1 - acc.equity / acc.peak
    acc["daily_used"] = (-acc.day_realised / (cfg.risk.daily_loss_stop_pct * acc.day_start_equity)).clip(lower=0)
    view = pd.DataFrame({
        "Sub-bot": acc.account_id, "Equity": acc.equity.map(fmt.inr), "Peak": acc.peak.map(fmt.inr),
        "Drawdown": acc.drawdown.map(lambda x: fmt.pct(x, sign=False)),
        "Daily loss used": acc.daily_used.map(lambda x: fmt.pct(x, 0, sign=False)),
        "Losing streak": acc.consecutive_losses, "Halted": acc.halted.map(lambda h: "🛑 yes" if h else "no"),
    })
    st.dataframe(view, hide_index=True, width="stretch")
    st.caption(f"Active recovery policy: **{cfg.risk.recovery_policy}** · risk per trade {fmt.pct(cfg.risk.risk_pct, 2, sign=False)} "
               f"of current equity · daily stop {fmt.pct(cfg.risk.daily_loss_stop_pct, 0, sign=False)} · kill-switch at "
               f"{fmt.pct(cfg.risk.max_drawdown_pct, 0, sign=False)} below peak.")
    if (acc.pending_deposit > 0).any():
        st.warning("A large deposit is waiting for your confirmation before the bigger risk budget applies.")
        if st.button("Confirm deposits", width="stretch"):
            ui.send("CONFIRM_DEPOSIT")
    halted = acc[acc.halted]
    if not halted.empty:
        st.error("Kill-switch tripped for: " + ", ".join(f"{r.account_id} ({r.halt_reason})" for r in halted.itertuples()))
        with st.form("reset"):
            st.write("Resuming after a kill-switch is a deliberate human decision. Review the losing trades first.")
            who = st.selectbox("Account", ["(all halted)"] + list(halted.account_id))
            phrase = st.text_input(f'Type "{HALT_CONFIRM_PHRASE}" to resume')
            if st.form_submit_button("Resume", width="stretch"):
                if phrase.strip() != HALT_CONFIRM_PHRASE:
                    st.error("The phrase does not match. Nothing changed.")
                else:
                    ui.send("HALT_RESET", phrase=phrase, **({} if who.startswith("(") else {"account_id": who}))

hist = ui.q("SELECT ts, message FROM events WHERE level='HALT' ORDER BY id DESC LIMIT 20")
with st.expander(f"Kill-switch history ({len(hist)})"):
    for r in hist.itertuples():
        st.markdown(f"- {fmt.ist(r.ts)} — {r.message}")

st.subheader("Recovery Lab")
st.caption("Monte-Carlo: the out-of-sample trade results are reshuffled 10,000 times (in blocks, to keep losing streaks) and each "
           "sizing policy is applied. Sizing rules cannot create an edge; they only change how much is at risk when losses come.")
summary = ui.kv("arena_summary", {}) or {}
labs = {k: v["lab"] for k, v in summary.items() if v.get("lab")}
if not labs:
    ui.empty("Run the arena first; strategies need 10+ out-of-sample trades for the lab.")
else:
    sid = st.selectbox("Strategy", list(labs), format_func=lambda k: f"{k} {summary[k]['name']}")
    lab = labs[sid]
    st.markdown(f"**Recommendation:** {lab['recommendation']}")
    tb = pd.DataFrame(lab["table"]).T
    tb = pd.DataFrame({"Policy": tb["name"], "Median end": tb.median_end.map(fmt.inr), "Bad case (5th pct)": tb.p5_end.map(fmt.inr),
                       "P(kill-switch)": tb.p_kill.map(lambda x: fmt.pct(x, 1, sign=False)),
                       "P(ruin, −50%)": tb.p_ruin.map(lambda x: fmt.pct(x, 1, sign=False)),
                       "Longest losing streak (median)": tb.longest_losing_median})
    st.dataframe(tb, width="stretch")
    fig = go.Figure()
    for pol, q in lab["fan"].items():
        fig.add_trace(go.Box(name=pol, q1=[q[1]], median=[q[2]], q3=[q[3]], lowerfence=[q[0]], upperfence=[q[4]]))
    st.plotly_chart(ui.plotly_layout(fig.update_layout(title="Ending equity spread (5th–95th percentile)"), 300), width="stretch")

st.subheader("Why Martingale is never allowed")
st.markdown("<div class='th-card' style='border-left:6px solid var(--th-live)'><b>RUIN DEMONSTRATION — simulator only, "
            "never selectable for paper or live.</b> Doubling the stake after every loss does not create an edge; "
            "it guarantees that an ordinary losing streak empties the account.</div>", unsafe_allow_html=True)
eq0 = cfg.capital.starting_paper_equity_inr
rows = martingale_ruin_table(eq0 * cfg.risk.risk_pct, eq0)
st.dataframe(pd.DataFrame([{"Losses in a row": r["losses"], "Total lost": fmt.inr(r["cumulative_loss"]),
                            "Next stake needed": fmt.inr(r["next_risk"]), "Money left": fmt.inr(r["left"]),
                            "Can continue?": "yes" if r["can_continue"] else "NO — account broken"} for r in rows]),
             hide_index=True, width="stretch")
st.caption(f"Starting from {fmt.inr(eq0 * cfg.risk.risk_pct)} risk on {fmt.inr(eq0)}. At a 50% win rate, 7 losses in a row has "
           "a 0.78% chance on any given trade — over hundreds of trades it is likely.")
