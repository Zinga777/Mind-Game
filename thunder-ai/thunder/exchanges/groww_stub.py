"""Groww adapter: documented stub. See docs/ADDING_AN_EXCHANGE.md.

Groww is an equities / F&O venue with different fees, hours and contract rules.
Do not assume it offers crypto. Strategy Cards validated on CoinDCX MUST NOT be
applied here without fresh research and re-validation.
"""
from __future__ import annotations


class GrowwAdapter:
    name = "groww"

    def __getattr__(self, item):
        def _nope(*a, **k):
            raise NotImplementedError("GrowwAdapter is a stub. See docs/ADDING_AN_EXCHANGE.md")
        return _nope
