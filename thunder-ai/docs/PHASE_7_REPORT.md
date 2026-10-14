# Phase 7 — Council

**What works:** seven deterministic analysts (candlestick, trend & structure, volume & momentum, levels/liquidity,
observable psychology, execution/cost, counter-analyst), one challenge round, the 100-point scorecard, hard
disqualifications and the four final states. Optional LLM council (`rules_plus_llm`): structured JSON, cached by
evidence hash, daily call and cost caps, refusal/invalid output = "no opinion".

**Tested:** H10 — the LLM can only approve, veto or reduce size (factor clamped ≤ 1); rules-only works with no key;
budget cap; caching.

**Not done:** the rules_only vs rules_plus_llm A/B comparison needs an Anthropic key and cached calls.
