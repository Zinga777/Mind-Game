# Adding an exchange

THUNDER talks to exchanges only through the `ExchangeAdapter` protocol in `thunder/exchanges/base.py`.
CoinDCX is the only implementation. `thunder/exchanges/groww_stub.py` is a deliberate stub.

**Do not assume Groww offers crypto.** Groww is an equities / F&O venue with different fees, trading hours,
lot sizes, margin rules and taxes. Before a single strategy runs there:

1. Research and document the venue in a new `docs/api_findings_<venue>.md` (endpoints, auth, limits, fees,
   contract specs, trading hours, settlement) — verified against official docs, with raw response fixtures.
2. Implement the adapter (public data first), plus a mock server for tests.
3. Extend the cost model (brokerage, STT, exchange charges, stamp duty, GST) and session-hours handling.
4. Re-run the full arena and paper stage on that venue's own data.

Strategy Cards are tagged with their exchange; the engine refuses a CoinDCX card on any other exchange.
