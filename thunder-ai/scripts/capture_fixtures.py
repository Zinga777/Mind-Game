"""Phase 0 on a networked machine: call each public CoinDCX endpoint once and save the raw
responses to tests/fixtures/live_*.json, then print a feasibility table. Read-only, no key."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.exchanges.coindcx.http import Http  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
API, PUB = "https://api.coindcx.com", "https://public.coindcx.com"


def main():
    h = Http(rate_per_s=2)
    calls = {
        "live_active_instruments_INR": ("GET", f"{API}/exchange/v1/derivatives/futures/data/active_instruments",
                                        {"margin_currency_short_name[]": "INR"}),
        "live_active_instruments_USDT": ("GET", f"{API}/exchange/v1/derivatives/futures/data/active_instruments",
                                         {"margin_currency_short_name[]": "USDT"}),
        "live_instrument_BTC_INR": ("GET", f"{API}/exchange/v1/derivatives/futures/data/instrument",
                                    {"pair": "B-BTC_USDT", "margin_currency_short_name": "INR"}),
        "live_trades_BTC": ("GET", f"{API}/exchange/v1/derivatives/futures/data/trades", {"pair": "B-BTC_USDT"}),
        "live_orderbook_BTC": ("GET", f"{PUB}/market_data/v3/orderbook/B-BTC_USDT-futures/50", None),
    }
    import time
    now = int(time.time())
    for res in ("1", "5", "15", "60", "1D"):
        calls[f"live_candles_BTC_{res}"] = ("GET", f"{PUB}/market_data/candlesticks",
                                            {"pair": "B-BTC_USDT", "from": now - 6 * 3600, "to": now, "resolution": res, "pcode": "f"})
    for name, (m, url, params) in calls.items():
        try:
            data = h.request(m, url, params=params)
            (OUT / f"{name}.json").write_text(json.dumps(data, indent=1)[:2_000_000])
            print(f"OK   {name}")
        except Exception as e:
            print(f"FAIL {name}: {e}")
    print("Now run: python scripts/feasibility.py --live")


if __name__ == "__main__":
    main()
