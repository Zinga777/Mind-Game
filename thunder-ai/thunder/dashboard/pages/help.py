from pathlib import Path

import streamlit as st

from thunder.dashboard import components as ui

ui.page_setup("Help")
st.title("❓ Help")
ROOT = Path(__file__).resolve().parents[3]

st.subheader("How THUNDER works")
st.markdown("""
```
 market data ──► checks (fresh? gaps?) ──► indicators & market type
        │
        ▼
 sub-bots (S1–S8) propose ideas ──► desk of analysts + scorecard ──► risk guard ──► paper order
        │                                                                   │
        └──────────── every trade, rejection and reason is recorded ◄────────┘
                                  │
                arena ranks strategies on UNSEEN data after ALL costs
                                  │
       Strategy Card  ──►  30+ days paper  ──►  locked live switch (owner decides)
```
""")
st.subheader("Glossary")
for k, v in ui.GLOSSARY.items():
    st.markdown(f"- **{k}** — {v}")

st.subheader("Why small accounts live or die on costs")
st.markdown("""
The break-even win rate after costs is **p\\* = (1 + cost_R) / (RR + 1)**. With a reward-to-risk of 1.5: costs of
0.10R → 44% wins needed; 0.25R → 50%; 0.40R → 56%. With RR 1.0 and costs 0.25R you need 62.5% wins before earning
anything. On ₹3,000 with a 0.5% stop, taker fees on both sides are about ₹3.54 on ₹3,000 of exposure — roughly a
quarter of the ₹15 risk. That is why THUNDER prefers limit (maker) entries, uses wider stops instead of scalping tiny
moves, and refuses trades whose costs exceed 30% of the risk.
""")
st.subheader("Keep the laptop awake")
st.markdown("""
- Keep it **plugged in** and the lid open (or set "do nothing when lid closes").
- **Windows:** Settings → System → Power → Screen and sleep → "Never" when plugged in.
- **macOS:** System Settings → Battery → Options → "Prevent automatic sleeping when the display is off".
- THUNDER also asks the computer not to sleep while the engine runs (best effort).
""")
st.subheader("Back up / update")
st.markdown("""
- Back up: copy the **data** folder (a daily automatic copy is kept in data/backups). Run `scripts/backup_db.py` any time.
- Update: stop THUNDER, replace the program files (keep `data/` and `config.yaml`), start it again.
- Always-on cloud server: see `docs/DEPLOY_VPS.md`.
""")
st.subheader("CoinDCX terms & your responsibility")
st.warning("CoinDCX's API terms restrict redistributing market data and make you responsible for any licence needed "
           "for algorithmic trading under applicable law. THUNDER therefore binds the dashboard to this computer only "
           "(127.0.0.1) and never publishes market data. Please confirm your own regulatory position. Tax figures are "
           "estimates — confirm with a chartered accountant.")
st.subheader("Why these safeguards exist")
st.markdown("""
- Many strategies look profitable in backtests because they were tuned on the same data they were tested on, or because
  costs, slippage and funding were ignored. Splits, controls, trial counting and cost-stress tests catch that.
- Very small accounts face a high fixed cost per trade, so cost_R, maker-vs-taker and minimum-order feasibility are first-class checks.
- Sizing rules cannot create an edge. If net expectancy per trade is not positive, no recovery policy fixes it.
- Automation removes emotion, not risk: outages, API changes, fast markets and bugs can all cause losses — hence
  kill-switches, exchange-side stops, reconciliation, the staged unlock and the first-20-trades approval.
""")
st.subheader("Known limitations")
kl = ROOT / "docs" / "KNOWN_LIMITATIONS.md"
st.markdown(kl.read_text(encoding="utf-8") if kl.exists() else "See docs/KNOWN_LIMITATIONS.md")
