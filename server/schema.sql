-- Mind Athlete — local development schema (SQLite).
--
-- This mirrors the shape of the production Postgres schema described in the
-- README (users, game_attempts, ratings, coin ledger, ...) closely enough
-- that porting to Postgres later is a dialect change, not a redesign.
-- `tournaments` / `tournament_participants` are reserved but unused in this
-- phase — see README roadmap.

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE,
  password_hash TEXT,
  is_guest INTEGER NOT NULL DEFAULT 1,
  display_name TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS game_attempts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  objective TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  mutators TEXT NOT NULL, -- JSON array
  seed TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  final_score INTEGER NOT NULL,
  base_score INTEGER NOT NULL,
  speed_bonus INTEGER NOT NULL,
  combo_bonus INTEGER NOT NULL,
  time_bonus INTEGER NOT NULL,
  penalties INTEGER NOT NULL,
  accuracy REAL NOT NULL,
  avg_reaction_ms INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  incorrect_count INTEGER NOT NULL,
  best_combo INTEGER NOT NULL,
  played_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_leaderboard
  ON game_attempts (objective, difficulty, final_score DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON game_attempts (user_id, played_at DESC);

CREATE TABLE IF NOT EXISTS personal_bests (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  objective TEXT NOT NULL,
  best_score INTEGER NOT NULL,
  attempt_id TEXT NOT NULL REFERENCES game_attempts(id),
  achieved_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, objective)
);

CREATE TABLE IF NOT EXISTS streaks (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  current_streak INTEGER NOT NULL DEFAULT 0,
  longest_streak INTEGER NOT NULL DEFAULT 0,
  last_played_date TEXT
);

CREATE TABLE IF NOT EXISTS coin_wallets (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  balance INTEGER NOT NULL DEFAULT 0
);

-- Server-authoritative ledger. The client never sets `amount` or `balance_after`
-- directly — every row here is written by a trusted server operation.
CREATE TABLE IF NOT EXISTS coin_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL, -- EARNED | SPENT | ADJUSTED ...
  amount INTEGER NOT NULL,
  balance_before INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  source TEXT NOT NULL, -- e.g. 'ad_reward', 'personal_best', 'daily_login'
  reference_id TEXT,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  placement TEXT NOT NULL, -- 'post_game_reward'
  status TEXT NOT NULL, -- 'started' | 'completed' | 'skipped'
  reward_coins INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

-- Reserved for the tournament phase (see README roadmap). Not read or
-- written by any route yet — created now so the eventual feature is a data
-- migration away, not a schema redesign.
CREATE TABLE IF NOT EXISTS tournaments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  config TEXT NOT NULL, -- JSON: format, games, difficulty, mutators, entry, prizes
  created_by TEXT REFERENCES users(id),
  created_at INTEGER NOT NULL
);
