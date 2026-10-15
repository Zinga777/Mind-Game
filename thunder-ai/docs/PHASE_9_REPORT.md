# Phase 9 — Strategy Cards + Live (locked)

**What works:** versioned, secret-free Strategy Cards (JSON + printable page) with code/config hash tamper check and
exchange tag; Live page with the gate checklist, masked key entry (OS keyring / owner-only file), read-only
connection test, typed phrase, arm, first-20-trades approval, EXIT ALL & HALT; live executor (exchange-side TP/SL
immediately after fill; failure ⇒ market exit + HALT; 3 rejections ⇒ halt; clock-skew check); live reconciler
every 10 s; smoke-test script.

**Tested against the mock exchange:** live is disabled by default and every gate is required; config alone cannot
enable it; HMAC signing matches the documented scheme; protective-order failure ⇒ exit + halt; EXIT ALL; the bot
never calls withdrawal/transfer endpoints; reconciler mismatch ⇒ halt.

**Not verified:** everything live is `UNVERIFIED_AGAINST_LIVE_EXCHANGE` until the owner runs the smoke test.
