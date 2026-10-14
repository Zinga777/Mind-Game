# Phase 0 — Verify

**What works:** every API claim in the spec is listed in `api_findings.md` with its source and status. A
feasibility table for ₹3,000/₹10,000/₹25,000/₹1,00,000 is in `feasibility.md`. Decisions are in `DECISIONS.md`.

**What could not be verified:** all of it against the live exchange — the build machine's network policy blocked
every CoinDCX host. Status for every claim is therefore **unknown**, and the claims come from the spec and an
unofficial client library. Fixtures in `tests/fixtures/` mirror the documented shapes; they are not captured responses.

**Key finding:** under the assumed contract sizes, ₹3,000 at 0.5% risk cannot trade any instrument with a stop
wide enough to pay its costs. Recommendations (not applied silently) are in `feasibility.md`.

**Gate:** every claim is marked (here: unknown). Passed with that caveat.
