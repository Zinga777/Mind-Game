# Phase 0 feasibility table

Source: ASSUMED prices and minimum quantities (UNVERIFIED — CoinDCX was unreachable at build time). Taker fees 0.05% both sides + 18% GST, risk 0.5% of capital, INR/USDT 88.0, leverage cap 5x.

| Capital | Instrument | Risk budget | Min order notional | All-in risk of min order at stop 0.3% / 0.5% / 1% / 2% | Feasible stops (budget AND cost_R <= 0.30) |
|---|---|---|---|---|---|
| ₹3,000 | B-BTC_USDT | ₹15 | ₹8,800 | ₹43 / ₹61 / ₹104 / ₹192 | **none** |
| ₹3,000 | B-ETH_USDT | ₹15 | ₹3,520 | ₹17 / ₹24 / ₹42 / ₹77 | **none** |
| ₹3,000 | B-SOL_USDT | ₹15 | ₹1,760 | ₹9 / ₹12 / ₹21 / ₹38 | **none** |
| ₹3,000 | B-XRP_USDT | ₹15 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | **none** |
| ₹3,000 | B-DOGE_USDT | ₹15 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | **none** |
| ₹10,000 | B-BTC_USDT | ₹50 | ₹8,800 | ₹43 / ₹61 / ₹104 / ₹192 | **none** |
| ₹10,000 | B-ETH_USDT | ₹50 | ₹3,520 | ₹17 / ₹24 / ₹42 / ₹77 | 1.0% |
| ₹10,000 | B-SOL_USDT | ₹50 | ₹1,760 | ₹9 / ₹12 / ₹21 / ₹38 | 1.0%, 2.0% |
| ₹10,000 | B-XRP_USDT | ₹50 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |
| ₹10,000 | B-DOGE_USDT | ₹50 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |
| ₹25,000 | B-BTC_USDT | ₹125 | ₹8,800 | ₹43 / ₹61 / ₹104 / ₹192 | 1.0% |
| ₹25,000 | B-ETH_USDT | ₹125 | ₹3,520 | ₹17 / ₹24 / ₹42 / ₹77 | 1.0%, 2.0% |
| ₹25,000 | B-SOL_USDT | ₹125 | ₹1,760 | ₹9 / ₹12 / ₹21 / ₹38 | 1.0%, 2.0% |
| ₹25,000 | B-XRP_USDT | ₹125 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |
| ₹25,000 | B-DOGE_USDT | ₹125 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |
| ₹100,000 | B-BTC_USDT | ₹500 | ₹8,800 | ₹43 / ₹61 / ₹104 / ₹192 | 1.0%, 2.0% |
| ₹100,000 | B-ETH_USDT | ₹500 | ₹3,520 | ₹17 / ₹24 / ₹42 / ₹77 | 1.0%, 2.0% |
| ₹100,000 | B-SOL_USDT | ₹500 | ₹1,760 | ₹9 / ₹12 / ₹21 / ₹38 | 1.0%, 2.0% |
| ₹100,000 | B-XRP_USDT | ₹500 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |
| ₹100,000 | B-DOGE_USDT | ₹500 | ₹2,200 | ₹11 / ₹15 / ₹26 / ₹48 | 1.0%, 2.0% |

## What this means

- Stops tighter than about 0.6% cannot pay for themselves: taker fees + GST + slippage are ~0.19% of price, so a 0.5% stop already spends ~38% of the risk on costs (limit is 30%).
- With **₹3,000** and 0.5% risk (₹15), under these assumptions **no instrument is tradeable**: wide-enough stops make even the minimum order cost more than ₹15 to lose. Every such candidate is rejected as **UNDERCAPITALISED** — the bot never rounds up or widens risk to participate. From about **₹10,000** the cheaper perpetuals become feasible; BTC needs roughly ₹25,000+.
- Recommendations (owner decides; nothing is changed silently): (1) research on lower-priced liquid perpetuals (e.g. XRP/DOGE-class instruments whose minimum order is small) — add them in Settings → Instruments after they pass the liquidity filter; (2) use a larger *paper* capital (₹25,000+) to measure edge; (3) only as a last resort, a higher risk %, which increases losses per trade.
