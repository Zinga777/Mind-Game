# Phase 8 — Paper engine 24/7

**What works:** candle-close scheduler, demo virtual clock, persistence after every batch, replay of missed candles
(no new entries on old data), deterministic feature windows, reconciler (DB ↔ memory), events & alerts (Telegram /
email optional, off by default), rotating scrubbed logs with error IDs, daily backup and insight report, uptime
tracking, Dockerfile + docker-compose, VPS guide.

**Tested:** **soak test** — 90 days replayed through the real-time engine path with 6 random kill/restarts produce
trades and account states identical to an uninterrupted run; command round-trip; corrupted state ⇒ the engine
refuses to start (H14).
