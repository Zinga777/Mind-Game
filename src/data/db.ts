import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { GameConfig, ObjectiveType, ScoreBreakdown, SelectionEvent } from '../game-engine/types'

/**
 * Mind Athlete is local-first: everything the player does works offline,
 * with no account and no server round-trip. IndexedDB is the single source
 * of truth. Every store below is shaped so a future cloud-sync phase could
 * mirror it to a server without a redesign (see README) — but nothing here
 * talks to a network.
 */

export interface PlayerProfileRecord {
  id: 'singleton'
  username: string
  avatarId: string
  createdAt: number
}

export interface GameAttemptRecord {
  id: string
  config: GameConfig
  events: SelectionEvent[]
  score: ScoreBreakdown
  isPersonalBest: boolean
  thunderEarned: number
  playedAt: number
}

export interface PersonalBestRecord {
  objective: ObjectiveType
  bestScore: number
  attemptId: string
  achievedAt: number
}

export interface GhostRunRecord {
  objective: ObjectiveType
  config: GameConfig
  events: SelectionEvent[]
  finalScore: number
  recordedAt: number
}

export type ThunderTransactionType = 'EARNED' | 'SPENT' | 'ADJUSTED'

export interface ThunderTransactionRecord {
  transactionId: string
  timestamp: number
  type: ThunderTransactionType
  amount: number
  balanceAfter: number
  source: string
  challengeId?: string
  dedupeKey?: string
}

export interface AchievementUnlockRecord {
  id: string
  unlockedAt: number
}

export interface DailyChallengeRecord {
  dateKey: string
  attempted: boolean
  completed: boolean
  score: number | null
  isPersonalBest: boolean
  attemptId: string | null
}

export interface StreakRecord {
  id: 'singleton'
  current: number
  longest: number
  lastPlayedDateKey: string | null
}

export interface SettingsRecord {
  id: 'singleton'
  sfxEnabled: boolean
  musicEnabled: boolean
  hapticsEnabled: boolean
  reduceMotion: boolean
  masterVolume: number
}

export interface AdFrequencyRecord {
  id: 'singleton'
  gamesSincePlayedTotal: number
  gamesSinceLastInterstitial: number
  lastInterstitialAt: number | null
  rewardedAdsWatchedToday: number
  rewardedAdsDayKey: string | null
  firstSessionAt: number
}

interface MindAthleteDB extends DBSchema {
  profile: { key: 'singleton'; value: PlayerProfileRecord }
  gameHistory: {
    key: string
    value: GameAttemptRecord
    indexes: { byPlayedAt: number; byObjective: string }
  }
  personalBests: { key: string; value: PersonalBestRecord }
  ghostRuns: { key: string; value: GhostRunRecord }
  thunderLedger: {
    key: string
    value: ThunderTransactionRecord
    indexes: { byTimestamp: number; byDedupeKey: string }
  }
  achievements: { key: string; value: AchievementUnlockRecord }
  dailyChallenge: { key: string; value: DailyChallengeRecord }
  streak: { key: 'singleton'; value: StreakRecord }
  settings: { key: 'singleton'; value: SettingsRecord }
  adFrequency: { key: 'singleton'; value: AdFrequencyRecord }
}

const DB_NAME = 'mind-athlete'
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<MindAthleteDB>> | null = null

export function getDb(): Promise<IDBPDatabase<MindAthleteDB>> {
  if (!dbPromise) {
    dbPromise = openDB<MindAthleteDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        db.createObjectStore('profile', { keyPath: 'id' })

        const history = db.createObjectStore('gameHistory', { keyPath: 'id' })
        history.createIndex('byPlayedAt', 'playedAt')
        history.createIndex('byObjective', 'config.objective')

        db.createObjectStore('personalBests', { keyPath: 'objective' })
        db.createObjectStore('ghostRuns', { keyPath: 'objective' })

        const ledger = db.createObjectStore('thunderLedger', { keyPath: 'transactionId' })
        ledger.createIndex('byTimestamp', 'timestamp')
        // unique: a second write with the same dedupeKey throws rather than
        // silently inserting a duplicate — closes the check-then-write race
        // that two concurrent callers (e.g. React StrictMode's double-invoked
        // effect) would otherwise hit.
        ledger.createIndex('byDedupeKey', 'dedupeKey', { unique: true })

        db.createObjectStore('achievements', { keyPath: 'id' })
        db.createObjectStore('dailyChallenge', { keyPath: 'dateKey' })
        db.createObjectStore('streak', { keyPath: 'id' })
        db.createObjectStore('settings', { keyPath: 'id' })
        db.createObjectStore('adFrequency', { keyPath: 'id' })
      },
    })
  }
  return dbPromise
}

export type { MindAthleteDB }
