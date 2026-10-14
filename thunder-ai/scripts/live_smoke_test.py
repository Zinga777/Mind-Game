"""Live smoke test (spec 17, gate 6). UNVERIFIED_AGAINST_LIVE_EXCHANGE.

Places ONE minimum-size BUY LIMIT order at half the current price (it cannot fill),
checks it is open, cancels it, checks it is cancelled, and records the result.
Run it once yourself after saving your API key on the Live page:
    python scripts/live_smoke_test.py            (real CoinDCX)
    python scripts/live_smoke_test.py --mock     (offline rehearsal against the mock exchange)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.config import load_config  # noqa: E402
from thunder.db import connect  # noqa: E402
from thunder.exchanges.coindcx import CoinDCXPrivate, CoinDCXPublic  # noqa: E402
from thunder.exchanges.coindcx.http import Http  # noqa: E402
from thunder.execution.live import smoke_test  # noqa: E402
from thunder.secrets import get_secret  # noqa: E402


def main() -> None:
    cfg = load_config()
    con = connect()
    pair = cfg.exchange.instruments[0]
    if "--mock" in sys.argv:
        from thunder.exchanges.mock_server import MockCoinDCX
        m = MockCoinDCX()
        pub = CoinDCXPublic(Http(session=m), margin_currency=cfg.exchange.margin_currency)
        priv = CoinDCXPrivate(m.api_key, m.api_secret, Http(session=m), margin_currency=cfg.exchange.margin_currency)
    else:
        key, sec = get_secret("coindcx_api_key"), get_secret("coindcx_api_secret")
        if not key or not sec:
            print("No API key saved. Save it on the Live page first.")
            return
        pub = CoinDCXPublic(Http(), cfg.exchange.api_base, cfg.exchange.public_base, cfg.exchange.margin_currency)
        priv = CoinDCXPrivate(key, sec, api_base=cfg.exchange.api_base, margin_currency=cfg.exchange.margin_currency)
    spec = pub.instrument_spec(pair)
    mid = pub.orderbook(pair).mid
    far = round(mid * 0.5 / spec.tick) * spec.tick
    print(f"Placing a {spec.min_qty} {pair} buy limit at {far} (market ~{mid:.2f}); it should never fill…")
    res = smoke_test(con, priv, pair, far, spec.min_qty)
    for step, ok in res["steps"]:
        print(f"  {'OK ' if ok else 'FAIL'} {step}")
    print("SMOKE TEST PASSED" if res["ok"] else "SMOKE TEST FAILED — live stays locked")
    if "--mock" in sys.argv:
        # a rehearsal must never unlock live trading
        from thunder.db import kv_set
        kv_set(con, "live_smoke_ok", {"ok": False, "note": "mock rehearsal only"})


if __name__ == "__main__":
    main()
