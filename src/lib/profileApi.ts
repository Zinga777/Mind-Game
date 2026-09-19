import { apiFetch } from './api'
import type { DifficultyLevel, GameConfig, ObjectiveType, ScoreBreakdown, SelectionEvent } from '../game-engine/types'

export interface ProfileResponse {
  user: { id: string; username: string | null; isGuest: boolean; displayName: string }
  coins: number
  personalBests: Partial<Record<ObjectiveType, number>>
  streak: { current: number; longest: number }
  recentRuns: { id: string; objective: ObjectiveType; difficulty: DifficultyLevel; finalScore: number; playedAt: number }[]
  totalRuns: number
}

export function fetchProfile(): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>('/profile')
}

export interface SubmitAttemptResponse {
  attemptId: string
  score: ScoreBreakdown
  isNewPersonalBest: boolean
  previousBest: number | null
  streak: { current: number; longest: number }
  coins: number
  globalRank: number
}

export function submitAttempt(payload: {
  config: GameConfig
  events: SelectionEvent[]
  remainingTimeMs: number
  bestCombo: number
}): Promise<SubmitAttemptResponse> {
  return apiFetch<SubmitAttemptResponse>('/game-attempts', { method: 'POST', body: payload })
}

export interface LeaderboardResponse {
  objective: string
  difficulty: string
  top: { rank: number; userId: string; displayName: string; bestScore: number }[]
  myBest: number | null
  myRank: number | null
}

export function fetchLeaderboard(objective: ObjectiveType, difficulty: DifficultyLevel): Promise<LeaderboardResponse> {
  return apiFetch<LeaderboardResponse>(`/leaderboard?objective=${objective}&difficulty=${difficulty}`)
}

export interface AdRewardResponse {
  rewardCoins: number
  coins: number
  remainingToday: number
}

export function claimAdReward(placement = 'post_game_reward'): Promise<AdRewardResponse> {
  return apiFetch<AdRewardResponse>('/ads/reward', { method: 'POST', body: { placement } })
}
