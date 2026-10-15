"""Phase 0 feasibility table (spec 11.2): for several capital sizes, can a 0.5%-risk trade
even buy the minimum order, and over which stop distances?

    python scripts/feasibility.py          # uses the ASSUMED specs/prices below (offline)
    python scripts/feasibility.py --live   # reads real min qty / step / price from CoinDCX

Writes docs/feasibility.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.trade.sizing import per_unit_loss  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPITALS = [3000.0, 10000.0, 25000.0, 100000.0]
RISK_PCT = 0.005
USDT_INR = 88.0
# ASSUMED (UNVERIFIED) — replace by running with --live on a networked machine.
ASSUMED = {
    "B-BTC_USDT": {"price": 100000.0, "min_qty": 0.001},
    "B-ETH_USDT": {"price": 4000.0, "min_qty": 0.01},
    "B-SOL_USDT": {"price": 200.0, "min_qty": 0.1},
    "B-XRP_USDT": {"price": 2.5, "min_qty": 10.0},
    "B-DOGE_USDT": {"price": 0.25, "min_qty": 100.0},
}
STOPS = [0.003, 0.005, 0.01, 0.02]


def rows(specs: dict) -> list[str]:
    out = ["| Capital | Instrument | Risk budget | Min order notional | All-in risk of min order at stop 0.3% / 0.5% / 1% / 2% | Feasible stops (budget AND cost_R <= 0.30) |",
           "|---|---|---|---|---|---|"]
    for cap in CAPITALS:
        budget = cap * RISK_PCT
        for pair, s in specs.items():
            p, q = s["price"], s["min_qty"]
            notional = p * q * USDT_INR
            risks = []
            ok = []
            for st in STOPS:
                # all-in loss at the stop incl. taker fees, GST and 2 + 5 bps slippage
                r = per_unit_loss(p, p * (1 - st), 0.0005, 0.0005, 0.18, p * 0.0002, p * 0.0005) * q * USDT_INR
                cost_r = r / (p * st * q * USDT_INR) - 1
                risks.append(f"₹{r:,.0f}")
                lev_ok = notional / cap <= 5
                if r <= budget and lev_ok and cost_r <= 0.30:
                    ok.append(f"{st:.1%}")
            out.append(f"| ₹{cap:,.0f} | {pair} | ₹{budget:,.0f} | ₹{notional:,.0f} | {' / '.join(risks)} | "
                       f"{', '.join(ok) if ok else '**none**'} |")
    return out


def main():
    specs = ASSUMED
    src = "ASSUMED prices and minimum quantities (UNVERIFIED — CoinDCX was unreachable at build time)"
    if "--live" in sys.argv:
        from thunder.exchanges.coindcx import CoinDCXPublic
        cl = CoinDCXPublic(margin_currency="INR", usdt_inr_rate=USDT_INR)
        specs = {}
        for pair in cl.active_instruments("INR")[:15]:
            sp = cl.instrument_spec(pair)
            specs[pair] = {"price": cl.orderbook(pair).mid, "min_qty": sp.min_qty}
        src = "LIVE CoinDCX instrument endpoint and order book"
    lines = ["# Phase 0 feasibility table", "", f"Source: {src}. Taker fees 0.05% both sides + 18% GST, "
             f"risk {RISK_PCT:.1%} of capital, INR/USDT {USDT_INR}, leverage cap 5x.", ""] + rows(specs) + [
        "", "## What this means", "",
        "- Stops tighter than about 0.6% cannot pay for themselves: taker fees + GST + slippage are ~0.19% of price, so a "
        "0.5% stop already spends ~38% of the risk on costs (limit is 30%).",
        "- With **₹3,000** and 0.5% risk (₹15), under these assumptions **no instrument is tradeable**: wide-enough stops "
        "make even the minimum order cost more than ₹15 to lose. Every such candidate is rejected as **UNDERCAPITALISED** — "
        "the bot never rounds up or widens risk to participate. From about **₹10,000** the cheaper perpetuals become "
        "feasible; BTC needs roughly ₹25,000+.",
        "- Recommendations (owner decides; nothing is changed silently): (1) research on lower-priced liquid perpetuals "
        "(e.g. XRP/DOGE-class instruments whose minimum order is small) — add them in Settings → Instruments after they "
        "pass the liquidity filter; (2) use a larger *paper* capital (₹25,000+) to measure edge; (3) only as a last resort, a "
        "higher risk %, which increases losses per trade.",
    ]
    (ROOT / "docs" / "feasibility.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
