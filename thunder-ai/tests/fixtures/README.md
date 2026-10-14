# Fixtures

These JSON files mirror the response SHAPES documented for CoinDCX futures (spec 6.2 and the
third-party `coindcx` PyPI client docstrings). They are **not captured live responses**:
the CoinDCX API and documentation hosts were unreachable from the build environment
(proxy policy 403). See `docs/api_findings.md`. When run on a networked machine,
`scripts/capture_fixtures.py` saves real responses next to these for comparison.
