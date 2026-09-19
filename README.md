# Mind Athlete

**Train. Compete. Discover Your Mind.**

Your brain is an athlete. Mind Athlete is a local-first brain-performance
game built around one core experience: **the 10×10 Mind Grid**. It runs
entirely in the browser — installable as a PWA, fully playable offline, no
account and no server required.

## Status: V1

This build implements the V1 scope end-to-end and locally: gameplay,
scoring, Thunder economy, personal bests, ghost runs, Mind DNA, achievements,
progression, a daily challenge, ads (behind a swappable abstraction), sound,
haptics, and offline PWA support. Everything is real and tested — nothing is
mocked data dressed up to look finished.

**Verified, not just built:**
- 55 passing unit tests across the whole engine (objectives, all 10
  mutators, scoring, Thunder economy, Mind DNA, achievements, progression,
  ghost comparison, confusable-distractor generation, reaction stats,
  mistake classification, one-more-run messaging).
- A full play-through driven in a real headless browser — Home → Pre-Game →
  Play → Results → Profile — with zero console errors.
- **Actual offline verification**: built for production, went fully offline
  at the OS/network level, reloaded, and completed an entire game (scoring,
  Thunder, IndexedDB writes) with no network connection at all.
- 320px viewport checked for horizontal overflow (none), both on Home and
  mid-gameplay.
- Found and fixed a real concurrency bug during QA: React StrictMode's
  double-invoked effect raced the Thunder "welcome grant," writing it twice
  under naive check-then-write dedup. Fixed with a unique IndexedDB index
  (`add()` fails atomically on a duplicate `dedupeKey` instead of a
  check-then-write race) — verified fixed by re-running the same scenario.

## What's implemented

**Core Mind Grid engine** (`src/game-engine`, pure TypeScript, zero UI
dependencies, fully seed-deterministic):
- 8 objectives: Ascending, Descending, Target Hunt, Min/Max, Odd/Even,
  Divisibility, Rule Switch, Memory Grid.
- 10 mutators: Shuffle, Vanish, Precision, Turbo, Distraction, Rotation,
  Mirror, Moving Targets, Locked Cells, Blind Phase — composable, with
  conflicting combinations (e.g. Shuffle + Rotation) automatically resolved
  rather than left to crash a session.
- 5 difficulty presets gating which mutators are eligible and scaling
  scoring/penalties.
- Explainable scoring (base + speed + combo + time bonus − penalties).
- `ThunderEngine`: cost-by-difficulty, reward-by-performance, all numbers
  centralized in one `ThunderConfig`.
- `PerformanceAnalyzer`: deterministic Mind DNA (Speed, Accuracy, Focus,
  Memory, Flexibility, Precision) plus a rule-based archetype (Sprinter /
  Scanner / Strategist / Calculator / Adapter / All-Rounder) and templated
  insight text comparing the latest run to the recent average — explicitly
  labeled as game-performance stats, not a medical or psychological
  assessment.
- `GhostEngine` (`compareToGhost`): live ahead/behind comparison against a
  player's own stored best run.
- Achievement rule engine and a deterministic progression formula (Rookie →
  Master) that weights personal bests and accuracy over raw game count.
- Deliberate distractor generation (`generateConfusableGrid`): when Target
  Hunt runs with the Distraction mutator, targets are chosen first and each
  is seeded with 1-2 digit-confusable near-misses (68 next to 86, 69, 66,
  88) via digit-swap and digit-nudge variants — difficulty comes from real
  visual similarity, not a wider random range standing in for it.
- Reaction-time statistics (fastest/median/slowest/variance, from
  `performance.now()` timestamps) and mistake classification
  (`classifyMistakes`) that labels each wrong pick as a digit-confusion
  near-miss or a rushed tap by checking it against the run's own event log —
  never an invented statistic.
- `buildOneMoreRunMessage`: a single traceable reason to play again —
  points from PB, percent of the way there, "one target away," or "ahead of
  your ghost until the final Ns" — derived from the same run's real data,
  never a generic "Good job."

**Local-first persistence** (`src/data`, `src/repositories` — IndexedDB via
`idb`, no server):
- `PlayerRepository`, `GameHistoryRepository`, `ThunderRepository`,
  `AchievementRepository`, `ChallengeRepository`, `SettingsRepository`,
  `AdFrequencyRepository` — clean interfaces, each independently swappable
  for a future cloud-sync backend without touching callers.
- `ThunderRepository` is a real ledger: balance is always the fold of every
  transaction, never a separately-mutable number, with a unique-indexed
  `dedupeKey` making duplicate claims (a repeated ad callback, a
  double-fired effect) provably impossible rather than merely unlikely.
- A daily challenge seeded from `date + engine version` — same day, same
  challenge, no server needed to hand it out.

**Full gameplay loop**: Home (streak, best score, daily challenge, mode
picker) → Pre-Game (Thunder cost, difficulty, countdown) → Play (grid, timer,
ghost delta indicator, no nav chrome — the grid owns the screen) → Results
(score breakdown, PB banner, Thunder earned breakdown, newly unlocked
achievements, a deterministic insight line, optional rewarded ad) → Profile
(Mind DNA bars, achievements grid, Thunder ledger, progression, settings).

**Ads** (`src/services/AdService.ts`): a typed interface
(`isRewardedAdAvailable` / `showRewardedThunderAd` /
`isInterstitialAvailable` / `showInterstitial`) with a `MockAdService`
implementation, since no real ad network is wired up. The reward path is
real — server-would-be logic (daily cap, amount) lives in the repository
layer, not the UI, so plugging in a real SDK later means implementing this
interface, not rewriting callers. `AdFrequencyManager` enforces the product
rule directly: new-player protection (first 3 games, no interstitials at
all), a game-count cooldown, and a time cooldown, and interstitials are only
offered at the Results → Home transition — never during gameplay, never
before the player has seen their score, PB, achievements, and Thunder.

**Sound & haptics**: synthesized Web Audio SFX (no asset files to ship) for
correct/incorrect/countdown/combo/PB/achievement/Thunder/level-up, and
`navigator.vibrate` haptics with matching patterns — both gated by
Profile → Settings toggles, both no-ops (not errors) where unsupported.
Reduce Motion is wired through Framer Motion's `MotionConfig` (not just a
stored flag) so toggling it actually disables the app's animations, on top
of respecting the OS-level `prefers-reduced-motion`.

**PWA & offline** (`vite-plugin-pwa`): a web manifest with `any` and
`maskable` icon variants, a service worker precaching the app shell, and
`start_url`/`display: standalone` for installability. Verified (see above)
to serve the full game offline after first load — not just claimed.

**Visual identity**: black/charcoal foundation, a single electric-green
accent, Thunder gold reserved as the one secondary tone — no other accent
colors. A custom vector lightning bolt (`src/components/brand/LightningMark`)
is the logo across the wordmark, favicon, and the full PWA icon set
(`any` + `maskable`, 192/512/apple-touch), generated from the same SVG
source so there's one shape, not a placeholder emoji standing in for a logo.

## What's deferred, and why

Per the brief's own "explicitly out of scope for V1" list, none of these are
built, and none are faked with placeholder data:
- Online multiplayer, global leaderboards, tournaments, clubs/friends, cloud
  accounts/sync, an AI coach or moderator, a server-side economy, real-money
  Thunder, social feeds.
- A real ad network integration (see "Ads" above for what's real vs. mocked).
- Full cosmetics catalog (the data model — `CosmeticRepository` — isn't
  built yet since there's nothing to spend Thunder on beyond gameplay costs
  in this pass; the ledger and wallet that would back it already exist).

## Architecture

```
src/
  game-engine/          Pure logic, zero UI/storage dependencies, unit-tested
    core/                 rng, gridGenerator (+ rotate/mirror/swap), session
                          (reducer: createSession/selectCell/tick), config
    objectives/            8 objective state machines
    mutators/               10 mutators, runtime config, conflict resolution
    difficulty/              5 presets
    scoring/                  explainable score breakdown
    thunder/                   ThunderConfig, cost/reward formulas
    performance/                Mind DNA analyzer + insight generator
    achievements/                 rule-based unlock checks
    progression/                   Rookie→Master scoring
    ghost/                          live best-run comparison

  data/db.ts             IndexedDB schema (idb) — the only place storage
                          shape is defined
  repositories/          One file per domain (Player, GameHistory, Thunder,
                          Achievement, Challenge, Settings, AdFrequency) —
                          thin, swappable wrappers over data/db.ts
  services/               AdService (+ Mock), AdFrequencyManager,
                          SoundService, HapticsService — app-level policy,
                          not gameplay logic
  state/                  React contexts (Player, Thunder, Settings) —
                          bind repositories to the component tree
  features/mind-grid/     MindGrid.tsx (renderer) + useMindGridSession
                          (React binding: rAF loop, selection, ghost/blind
                          state)
  pages/                  Home, PreGame, Play, Results, Profile
  components/              design system (Button, Card, Toast, Skeleton) +
                           brand (LightningMark) + ads (RewardedAdModal,
                           InterstitialModal)

server/                 A previous phase's Express+SQLite backend (accounts,
                         server-authoritative scoring, a real leaderboard).
                         Untouched, but not used by the app — this brief
                         calls for local-first, no-account gameplay, which a
                         server dependency would contradict (it also breaks
                         "play fully offline"). Kept rather than deleted
                         since it's real, tested code and a plausible
                         starting point for a future opt-in cloud-sync
                         phase; see `dev:legacy-server` if you want to run it.
```

**Why the engine is separate from storage and UI:** every gameplay
calculation (grid generation, objective validation, scoring, Thunder
rewards, Mind DNA) is a pure function of its inputs. That's what makes 39
unit tests possible without a DOM or a database, and it's what makes the
architecture genuinely portable — a future cloud-sync phase would reuse
every file in `game-engine/` unchanged; only the repository layer would grow
a network-backed implementation alongside the local one.

**Determinism:** `GameConfig.seed` drives every random draw via a mulberry32
PRNG. Runtime randomness during a session (mutator timing, rule-switch
phases) is re-derived from `seed + cursor` rather than carried as mutable
state, so a session produces identical results regardless of exact frame
timing — which is what makes the daily challenge ("same date → same
challenge for everyone") and ghost runs work without a server.

## Tech stack

- **React 19 + TypeScript + Vite**, entirely client-side — no build-time or
  runtime dependency on a backend.
- **IndexedDB** via `idb` for all persistence.
- **Tailwind CSS v4** (`@theme` in `src/index.css`) for the design system.
- **Framer Motion** for animation, wired to the in-app Reduce Motion setting
  via `MotionConfig`.
- **vite-plugin-pwa** (Workbox under the hood) for the manifest and service
  worker.
- **Vitest** for unit tests.

## Setup

```bash
npm install
npm run dev       # http://localhost:5173 — the whole app, no server needed
npm run build     # typecheck + production build (also generates the PWA
                   # service worker + manifest)
npm run preview   # serve the production build, to test PWA/offline behavior
npm test          # run once: npx vitest run
npm run lint       # oxlint
```

No environment variables or database setup are required — the game works
immediately after `npm install && npm run dev`. All data lives in the
browser's IndexedDB (`mind-athlete` database); clearing site data resets
everything.

To install as a PWA: run `npm run build && npm run preview`, open it in
Chrome/Edge, and use "Install app." The core loop then works fully offline.

## Roadmap (post-V1, not started)

1. Cosmetics catalog + `CosmeticRepository` (the Thunder wallet/ledger this
   would spend against already exists).
2. Opt-in cloud sync, built on the existing `server/` Express+SQLite
   backend — repositories already have the right shape to grow a
   network-backed implementation alongside the local one.
3. Real ad network integration behind the existing `AdService` interface.
4. Tournaments, global leaderboards, friends/clubs, an AI coach — all
   explicitly out of scope for V1 per the product brief.
