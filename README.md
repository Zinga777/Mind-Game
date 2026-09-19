# Mind Athlete

**Train. Compete. Discover Your Mind.**

Your brain is an athlete. Mind Athlete is a competitive brain-training platform
built around one core gameplay system: **the 10×10 Mind Grid**. Different
objectives, difficulty levels, and composable mutators create depth without
turning the product into a pile of unrelated mini-games.

## What's implemented in this build

The full product spec (tournaments, coin economy, AI coach, admin moderator,
social/leagues, ads, a Postgres-backed API, etc.) is a large, multi-phase
platform. Building all of it for real — not stubbed, not faked — requires
provisioned infrastructure (a database, auth provider, AI provider keys) that
doesn't exist in this environment. Rather than generate fake API responses,
hard-coded leaderboards, or invented user data to *look* complete, this build
delivers the non-negotiable core for real, end-to-end, and architects the rest
so it can be added without a rewrite:

**Working and tested:**
- The Mind Grid game engine (`src/game-engine`) — pure TypeScript, zero UI
  dependencies, deterministic from a seed (required for fair tournaments and
  reproducible daily challenges later).
- Objectives: Ascending, Descending, Target Hunt, Min/Max, Odd/Even,
  Divisibility, Rule Switch (phased objective changes mid-run), Memory Grid.
- Mutators: Shuffle, Vanish, Precision, Turbo, Distraction — composable, with
  incompatible combinations rejected (`shuffle` + `vanish`).
- Difficulty engine with 5 presets (Beginner → Master) that gate which
  mutators are allowed and scale scoring/penalties.
- A transparent, explainable scoring engine (base + speed + combo + time
  bonus − penalties = final score; every field is shown to the player).
- Full gameplay UI: Home → Pre-Game (difficulty/modifier picker + countdown)
  → Play (grid, timer, HUD) → Results (score breakdown, new-PB detection).
- Guest-mode local persistence (personal bests, streak, run history) behind a
  `ProfileStore`-shaped interface so it's a drop-in swap for a real backend.
- 16 passing unit tests covering seed reproducibility, every objective type,
  mutator validation, difficulty scaling, and the scoring engine's invariants
  (fields always sum to the final score; score never goes negative).
- Verified by driving the app in a real headless browser end-to-end (Home →
  Play → Results) with zero console/page errors — not just "the page loads."

**Explicitly not built (see "Roadmap" below), and not faked:**
- Accounts, auth, and a real database. There is no Postgres instance to
  connect to here, so there's no ORM/schema pretending to talk to one.
- Server-authoritative scoring/rating/leaderboards. Coins, rating, and rank
  must never be trusted from the client per the product spec — implementing
  them client-only would violate that principle, so the Leaderboard page says
  so instead of showing invented numbers.
- Tournaments, coin economy/ledger, AI Mind Coach, Mind Moderator admin
  dashboard, friends/social, ads, PWA/offline, i18n.

If you want the next phase built, the architecture below is designed so each
one is additive.

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
  state/                localProfileStore.ts — guest-mode persistence, typed
                         as the interface a future backend-backed store would
                         implement
  pages/                Home, PreGame, Play, Results, Leaderboard, Profile
  components/           Design system primitives (Button, Card, StatTile,
                         Badge) + AppShell (responsive nav)
```

**Why the engine is separate from React:** gameplay logic (grid generation,
objective validation, scoring) is pure and deterministic so it can be:
unit-tested without a DOM, reused server-side later for result validation
(never trust the client), and replayed byte-for-byte from a stored seed for
tournament fairness and historical reproducibility.

**Determinism:** `GameConfig.seed` drives every random draw via a mulberry32
PRNG (`SeededRng`). Runtime randomness during a session (shuffle timing, rule
phase changes) is re-derived from `seed + cursor` rather than carried as
mutable state, so a session tick loop produces identical results regardless
of exact frame timing — a prerequisite for validating tournament submissions
server-side against the same seed.

## Tech stack

- **React 19 + TypeScript + Vite** — chosen over Next.js because this phase
  is a client-only SPA with no server rendering or API routes yet; swapping
  in a backend later doesn't require this choice to change.
- **Tailwind CSS v4** (CSS-first config, `@theme` in `src/index.css`) for the
  design system — dark, premium, restrained accent colors per the product
  spec (no neon, no glassmorphism overload).
- **React Router** for client-side navigation between screens.
- **Vitest** for unit tests.

## Setup

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # typecheck + production build
npm test          # run once: npx vitest run
npm run lint       # oxlint
```

No environment variables are required to run this build — see
`.env.example` for what the backend phases will need and why nothing here
reads them yet.

## Roadmap (phases, per the product spec)

1. ~~Core Mind Grid engine~~ — done, this build.
2. ~~Polished gameplay UI~~ — done, this build.
3. Backend/database (Postgres, migrations, `users/games/game_attempts/...`
   schema from the spec) + an API layer that validates results server-side.
4. Auth (guest → registered account, session handling).
5. Server-authoritative scoring/rating/leaderboards.
6. Daily challenges, achievements, streak sync.
7. Tournaments (creation, escrow, lifecycle, reward distribution).
8. Coin economy + ledger (server-authoritative, non-cashable).
9. Cosmetics, friends/social, sharing.
10. Mind Coach (AI, tool-restricted, no direct DB/SQL access).
11. Mind Moderator (admin dashboard, economy/security monitoring).
12. Ads (behind an `AdService` abstraction), analytics, PWA, accessibility
    pass, production observability.

Each phase should be implemented against real infrastructure rather than
mocked, per the product's own "do not fake completeness" rule — which is why
they're listed here as not-yet-started rather than half-built.
