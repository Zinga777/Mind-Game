# Mind Athlete

**Train. Compete. Discover Your Mind.**

Your brain is an athlete. Mind Athlete is a competitive brain-training platform
built around one core gameplay system: **the 10×10 Mind Grid**. Different
objectives, difficulty levels, and composable mutators create depth without
turning the product into a pile of unrelated mini-games.

## What's implemented in this build

The full product spec (tournaments, AI coach, admin moderator, social/leagues,
i18n, a hosted Postgres deployment, etc.) is a large, multi-phase platform.
Rather than fake the parts that need infrastructure this environment doesn't
have, this build has a **real local backend** (Express + SQLite) and a
**real frontend wired to it** — not a client-only demo, and not stubbed API
responses:

**Working and tested:**
- The Mind Grid game engine (`src/game-engine`) — pure TypeScript, zero UI
  dependencies, deterministic from a seed. 8 objectives (Ascending,
  Descending, Target Hunt, Min/Max, Odd/Even, Divisibility, Rule Switch,
  Memory Grid), 5 composable mutators with conflict validation, 5 difficulty
  presets, an explainable scoring engine. 16 passing unit tests.
- **A local backend** (`server/`, Express + SQLite) that is the source of
  truth for accounts, scores, coins, and rankings — the frontend never
  invents this data:
  - Guest accounts created automatically on first visit (with a welcome
    coin grant), upgradeable to a real username/password account that keeps
    all progress.
  - **Server-side score validation**: the client sends the raw selection
    event log, not a final score. The server regenerates the grid from the
    submitted seed and rejects any event whose cell/value doesn't match what
    that seed would have produced, then computes the score itself from the
    engine's scoring function. A fabricated score or a fabricated cell value
    is rejected (422), not silently trusted.
  - A real coin wallet + auditable ledger (every grant/spend is a row with
    before/after balance, never a client-set number).
  - A real leaderboard (per objective + difficulty, ranked from actual
    stored attempts, with your rank shown even when you're off the top page).
  - Personal bests and streaks computed and stored server-side.
  - A rewarded-ad endpoint with a server-side daily cap and reward amount
    (see "Ads" below).
- Full gameplay UI: Home → Pre-Game (difficulty/modifier picker + countdown)
  → Play (grid, timer, HUD, live combo animation) → Results (score
  breakdown, real global rank, new-PB detection, rewarded-ad prompt).
  Leaderboard and Profile pages are backed by the API, with a guest → account
  upgrade flow that preserves everything.
- **Offline handling**: if a result fails to submit (server down, network
  drop), it's queued in `localStorage` and retried automatically on the next
  successful load instead of being silently dropped — the player still sees
  their locally-computed score immediately, flagged as unconfirmed.
- Motion/loading polish: page transitions, skeleton loaders while data
  fetches, a splash screen during session bootstrap, spring-animated combo
  and PB moments, toasts for coin rewards.
- Verified by driving the whole app (both servers running together) in a
  real headless browser: guest bootstrap → play a full round → server-
  validated results with real global rank → watch the placeholder ad → coins
  update → leaderboard shows real multi-user rankings → register an account
  → reload → session persists as the registered user. Zero console errors.
  `tsc -b`, `vitest run`, and `oxlint` all pass clean.

**Explicitly not built (see "Roadmap" below), and not faked:**
- Tournaments. The nav has a "Coming Soon" page instead of a working one,
  and the DB schema reserves a `tournaments` table, but there's no
  creation/registration/escrow/bracket flow — that needs product decisions
  (formats, entry rules) this pass didn't make up.
- A real ad network. Ads use a `RewardedAdModal` that plays a clearly-labeled
  placeholder timer instead of a real creative, behind the same
  show → wait-for-completion → claim-reward flow a real SDK would use, so
  swapping one in later doesn't change any caller.
- AI Mind Coach, Mind Moderator admin dashboard, friends/social, cosmetics,
  daily challenges, achievements, PWA/offline app shell, deep anti-cheat
  (timing/replay analysis beyond the cell-value check above), i18n.
- A **deployed** Postgres instance. The backend is real, tested code — SQLite
  today so it runs with zero external setup — but it hasn't been pointed at
  a hosted Postgres because none is provisioned here (see "Backend" below
  for how close that gap actually is).

## Architecture

```
src/
  game-engine/         Pure game logic — no React, no I/O, fully unit-tested
    core/               rng.ts (seeded PRNG), gridGenerator.ts, session.ts
                         (reducer: createSession/selectCell/tick), config.ts
    objectives/         Objective state machines + validation
    mutators/           Mutator runtime resolution + compatibility rules
    difficulty/         Difficulty presets
    scoring/            Explainable score breakdown
  features/mind-grid/   MindGrid.tsx (grid renderer) + useMindGridSession
                         (React binding: requestAnimationFrame loop, selection)
  lib/                  api.ts (fetch wrapper + token storage), profileApi.ts
                         (typed API calls)
  state/                SessionContext.tsx (auth bootstrap/register/login),
                         offlineQueue.ts (localStorage retry queue for failed
                         submissions)
  pages/                Home, PreGame, Play, Results, Leaderboard, Profile,
                         Tournaments (placeholder)
  components/           Design system primitives (Button, Card, StatTile,
                         Badge, Skeleton, Toast) + AppShell (responsive nav,
                         coin balance) + ads/RewardedAdModal

server/                 Express + SQLite — the backend, real and tested
  schema.sql            users, sessions, game_attempts, personal_bests,
                         streaks, coin_wallets, coin_ledger, ad_events,
                         tournaments (reserved, unused)
  db.ts                 SQLite connection + schema bootstrap
  lib/
    auth.ts              bearer-token sessions, guest account creation
    coins.ts              applyCoinTransaction — the only way coins move;
                          always transactional, always ledgered
    scoreValidation.ts    regenerates the grid from the submitted seed and
                          rejects attempts with fabricated cell values;
                          recomputes score from the event log server-side
  routes/                auth, profile, game-attempts, leaderboard, ads
```

**Why the engine is separate from React:** gameplay logic (grid generation,
objective validation, scoring) is pure and deterministic so it can be
unit-tested without a DOM, **imported directly by the server** for result
validation (never trust the client), and replayed byte-for-byte from a
stored seed for tournament fairness and historical reproducibility. The
server literally imports from `src/game-engine` — there's one scoring
implementation, not a client copy and a server copy that can drift.

**Determinism:** `GameConfig.seed` drives every random draw via a mulberry32
PRNG (`SeededRng`). Runtime randomness during a session (shuffle timing, rule
phase changes) is re-derived from `seed + cursor` rather than carried as
mutable state, so a session tick loop produces identical results regardless
of exact frame timing — which is what lets the server independently
regenerate the exact grid a client played on and check submitted events
against it.

## Tech stack

- **React 19 + TypeScript + Vite** on the frontend, **Express + SQLite**
  (via `better-sqlite3`) on the backend, run together with `concurrently`.
- SQLite, not Postgres, so the whole app runs with zero external setup —
  see "Backend" below for what porting to Postgres actually involves.
- **Tailwind CSS v4** (CSS-first config, `@theme` in `src/index.css`) for the
  design system — dark, premium, restrained accent colors.
- **Framer Motion** for the UI's micro-interactions (page transitions, combo
  pulses, PB celebration, splash screen, toasts).
- **React Router** for client-side navigation.
- **Vitest** for unit tests. **tsx** to run the TypeScript server directly in
  dev without a separate build step.

## Backend

This is a real backend, not a mock — it does I/O, persists to disk, and the
frontend has no fallback path that skips it (except the offline queue, which
exists specifically because the network can't be assumed reliable). What
makes it "local" rather than "production" is the database: `server/schema.sql`
is written in SQLite dialect but mirrors the shape of the Postgres schema the
product README originally called for (`users`, `game_attempts`,
`personal_bests`, `coin_wallets`, `coin_ledger`, ...). Moving to Postgres
means:
1. Swapping `better-sqlite3` for a Postgres client (e.g. `pg` or `postgres.js`).
2. Translating `schema.sql`'s SQLite-specific syntax (`INSERT ... ON CONFLICT`
   mostly carries over as-is; auto-increment/type syntax differs) into
   Postgres migrations.
3. Everything in `server/routes` and `server/lib` — auth, score validation,
   the coin ledger, the leaderboard queries — stays the same, since none of
   it depends on SQLite-specific behavior.

Auth is deliberately simple for this phase: bearer tokens in a `sessions`
table, `bcryptjs` password hashing, no JWT/refresh-token machinery. That's
enough for one server instance; a multi-instance production deployment would
want sessions in a shared store (Redis) or to move to signed JWTs.

## Ads

`RewardedAdModal` implements the `AdService` pattern the product spec calls
for: `show → wait for the viewer to finish → claim the reward`. There's no
real ad network account to integrate, so "show" is a clearly-labeled
placeholder timer instead of a real creative — but the reward path is real:
the server enforces a daily cap and decides the payout, exactly as it would
for a real network's server-to-server reward callback. Swapping in a real
SDK later means replacing the modal's internals, not the interface or the
server-side reward logic.

## Setup

```bash
npm install
npm run dev         # runs both: Vite (5173) + the API server (8787), proxied together
npm run dev:web      # frontend only
npm run dev:server   # backend only
npm run build        # typecheck + production build (frontend)
npm test             # run once: npx vitest run
npm run lint          # oxlint
```

The SQLite database is created automatically at `server/data/mind-athlete.sqlite`
on first run (gitignored). Delete that file to reset all local data.

No environment variables are required to run this build — see
`.env.example` for what a hosted deployment will need and why nothing here
reads them yet.

## Roadmap (phases, per the product spec)

1. ~~Core Mind Grid engine~~ — done.
2. ~~Polished gameplay UI~~ — done.
3. ~~Backend/database + server-authoritative scoring~~ — done locally
   (SQLite); porting to a hosted Postgres is the remaining step (see
   "Backend" above).
4. ~~Auth (guest → registered account)~~ — done.
5. ~~Leaderboards~~ — done, per objective/difficulty.
6. ~~Coin economy + ledger~~ — done (wallet, ledger, ad rewards, PB rewards);
   tournament entry/escrow still pending on tournaments themselves.
7. Daily challenges, achievements.
8. Tournaments (creation, registration, escrow, lifecycle, reward
   distribution) — schema reserved, nothing built on top of it yet.
9. Cosmetics, friends/social, sharing.
10. Mind Coach (AI, tool-restricted, no direct DB/SQL access).
11. Mind Moderator (admin dashboard, economy/security monitoring).
12. Real ad network integration, deeper anti-cheat (timing/replay analysis),
    analytics, PWA, accessibility pass, production observability, and
    deploying the Postgres version of the backend.

Each phase should be implemented against real infrastructure rather than
mocked, per the product's own "do not fake completeness" rule — which is why
they're listed here as not-yet-started rather than half-built.
