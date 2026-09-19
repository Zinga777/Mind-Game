import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { MindGrid } from '../features/mind-grid/MindGrid'
import { useMindGridSession } from '../features/mind-grid/useMindGridSession'
import { computeScore } from '../game-engine/scoring'
import { isRevealPhase } from '../game-engine/objectives'
import { isBlind } from '../game-engine/core/session'
import { compareToGhost } from '../game-engine/ghost'
import { computeThunderReward } from '../game-engine/thunder'
import { computeProgressionScore, levelForScore } from '../game-engine/progression'
import { evaluateAchievements, checkPbBreaker } from '../game-engine/achievements'
import { GameHistoryRepository } from '../repositories/GameHistoryRepository'
import { AchievementRepository } from '../repositories/AchievementRepository'
import { AdFrequencyManager } from '../services/AdFrequencyManager'
import { ChallengeRepository } from '../repositories/ChallengeRepository'
import { useThunder } from '../state/ThunderContext'
import { playSfx } from '../services/SoundService'
import { playHaptic } from '../services/HapticsService'
import type { GameConfig, SelectionEvent } from '../game-engine/types'
import type { GhostRunRecord } from '../data/db'

const COMBO_MILESTONES: { at: number; label: string }[] = [
  { at: 5, label: 'COMBO ACTIVE' },
  { at: 10, label: '⚡ OVERDRIVE' },
  { at: 15, label: '⚡ LOCKED IN' },
  { at: 20, label: '⚡ PERFECT RUN' },
]

function comboMilestoneLabel(combo: number): string | null {
  const exact = COMBO_MILESTONES.find((m) => m.at === combo)
  if (exact) return exact.label
  if (combo > 20 && combo % 5 === 0) return '⚡ PERFECT RUN'
  return null
}

type TimerPhase = 'normal' | 'pressure' | 'warning' | 'critical'

function timerPhaseFor(remainingMs: number): TimerPhase {
  if (remainingMs <= 4000) return 'critical'
  if (remainingMs <= 8000) return 'warning'
  if (remainingMs <= 15000) return 'pressure'
  return 'normal'
}

export function PlayPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as { config?: GameConfig; isDaily?: boolean } | null
  const config = state?.config

  if (!config) {
    navigate('/', { replace: true })
    return null
  }

  return <ActivePlaySession config={config} isDaily={Boolean(state?.isDaily)} />
}

function ActivePlaySession({ config, isDaily }: { config: GameConfig; isDaily: boolean }) {
  const navigate = useNavigate()
  const { earn } = useThunder()
  const hasSubmitted = useRef(false)
  const [ghost, setGhost] = useState<GhostRunRecord | null | undefined>(undefined)
  const [milestoneLabel, setMilestoneLabel] = useState<string | null>(null)
  const milestoneTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const everAheadOfGhostRef = useRef(false)
  const lastAheadElapsedMsRef = useRef<number | null>(null)
  const lastTickSecondRef = useRef<number | null>(null)

  useEffect(() => {
    GameHistoryRepository.getGhost(config.objective).then(setGhost)
  }, [config.objective])

  const onSelection = (event: SelectionEvent, comboAfter: number) => {
    if (event.correct) {
      playSfx('correct')
      playHaptic('correct')
      const label = comboMilestoneLabel(comboAfter)
      if (label) {
        playSfx('combo')
        playHaptic('combo')
        setMilestoneLabel(label)
        clearTimeout(milestoneTimeoutRef.current)
        milestoneTimeoutRef.current = setTimeout(() => setMilestoneLabel(null), 1100)
      }
    } else {
      playSfx('incorrect')
      playHaptic('incorrect')
    }
  }

  const { session, remainingMs, elapsedMs, select } = useMindGridSession(config, onSelection)

  const ghostComparison = ghost ? compareToGhost(ghost.events, elapsedMs, session.correctCount) : null

  // Track whether — and until when — the player held the lead over their ghost.
  useEffect(() => {
    if (!ghostComparison) return
    if (ghostComparison.status === 'ahead') {
      everAheadOfGhostRef.current = true
      lastAheadElapsedMsRef.current = elapsedMs
    }
  }, [ghostComparison, elapsedMs])

  // Final-seconds tension: a short tick as each whole second ticks down inside the critical window.
  useEffect(() => {
    if (session.status !== 'active') return
    const wholeSecond = Math.ceil(remainingMs / 1000)
    if (remainingMs <= 5000 && remainingMs > 0 && wholeSecond !== lastTickSecondRef.current) {
      lastTickSecondRef.current = wholeSecond
      playSfx('countdown')
      playHaptic('correct')
    }
  }, [remainingMs, session.status])

  useEffect(() => {
    if (session.status !== 'completed' || hasSubmitted.current) return
    hasSubmitted.current = true

    ;(async () => {
      const score = computeScore(session.events, config, remainingMs, session.bestCombo)
      const { attempt, isPersonalBest, previousBest, streak } = await GameHistoryRepository.recordAttempt({
        config,
        events: session.events,
        score,
        thunderEarned: 0,
      })

      if (isDaily) {
        await ChallengeRepository.recordCompletion(score.finalScore, isPersonalBest, attempt.id)
      }

      const [allHistory, allPbs] = await Promise.all([GameHistoryRepository.getAll(), GameHistoryRepository.getAllPersonalBests()])
      const totalGames = allHistory.length
      const pbCount = allHistory.filter((a) => a.isPersonalBest).length
      const averageAccuracy = allHistory.length === 0 ? 0 : allHistory.reduce((s, a) => s + a.score.accuracy, 0) / allHistory.length
      const progressionScore = computeProgressionScore({ totalGames, personalBestCount: allPbs.length, averageAccuracy })
      const progressionLevel = levelForScore(progressionScore)

      const historySamples = allHistory
        .slice(0, 20)
        .map((a) => ({ objective: a.config.objective, difficulty: a.config.difficulty, mutators: a.config.mutators, score: a.score, playedAt: a.playedAt }))
      const latestSample = historySamples[0] ?? {
        objective: config.objective,
        difficulty: config.difficulty,
        mutators: config.mutators,
        score,
        playedAt: Date.now(),
      }

      const unlockedIds = evaluateAchievements({ latest: latestSample, history: historySamples, progressionLevel })
      if (checkPbBreaker(pbCount)) unlockedIds.push('pb-breaker')

      const alreadyUnlocked = await AchievementRepository.getUnlocked()
      const newlyUnlocked: string[] = []
      for (const id of unlockedIds) {
        if (!alreadyUnlocked.has(id)) {
          const did = await AchievementRepository.unlock(id)
          if (did) newlyUnlocked.push(id)
        }
      }
      if (newlyUnlocked.length > 0) {
        playSfx('achievement')
        playHaptic('achievement')
      }
      if (isPersonalBest) {
        playSfx('pb')
        playHaptic('pb')
      } else {
        playSfx('gameOver')
      }

      const thunderReward = computeThunderReward({ score, isPersonalBest, newAchievementsCount: newlyUnlocked.length })
      await earn(thunderReward.total, 'game_reward', `attempt:${attempt.id}`)
      await GameHistoryRepository.updateThunderEarned(attempt.id, thunderReward.total)
      playSfx('thunder')

      await AdFrequencyManager.recordGamePlayed()

      const finalGhostComparison = ghost ? compareToGhost(ghost.events, config.durationSeconds * 1000, score.correctCount) : null

      navigate('/results', {
        state: {
          score,
          events: session.events,
          isNewPersonalBest: isPersonalBest,
          previousBest,
          streak,
          thunderReward,
          newlyUnlockedAchievements: newlyUnlocked,
          progressionLevel,
          config,
          ghost: ghost ?? null,
          ghostWasEverAhead: everAheadOfGhostRef.current,
          ghostLeadLostAtMs:
            everAheadOfGhostRef.current && finalGhostComparison?.status !== 'ahead' ? lastAheadElapsedMsRef.current : null,
        },
        replace: true,
      })
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.status])

  const isMemoryObjective =
    session.objective.type === 'memory' || (session.objective.type === 'rule-switch' && session.objective.sub.type === 'memory')
  const revealing = isRevealPhase(session.objective)
  const blind = isBlind(session, elapsedMs)
  const hideValues = (isMemoryObjective && !revealing) || blind

  const timerPhase = timerPhaseFor(remainingMs)
  const showDecimalTimer = timerPhase === 'critical'
  const timerColor =
    timerPhase === 'critical'
      ? 'text-danger-500'
      : timerPhase === 'warning'
        ? 'text-thunder-400'
        : timerPhase === 'pressure'
          ? 'text-thunder-500'
          : 'text-ink-50'
  const seconds = Math.ceil(remainingMs / 1000)
  const timerDisplay = showDecimalTimer
    ? (remainingMs / 1000).toFixed(2)
    : `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex w-full max-w-[560px] items-center justify-between">
        <motion.div
          animate={timerPhase === 'critical' ? { scale: [1, 1.08, 1] } : { scale: 1 }}
          transition={{ duration: 0.5, repeat: timerPhase === 'critical' ? Infinity : 0 }}
          className={`text-4xl font-black tabular-nums transition-colors ${timerColor}`}
        >
          {timerDisplay}
        </motion.div>
        {ghostComparison && (
          <div
            className={`rounded-full px-3 py-1 text-xs font-bold ${
              ghostComparison.status === 'ahead'
                ? 'bg-volt-500/15 text-volt-400'
                : ghostComparison.status === 'behind'
                  ? 'bg-danger-500/15 text-danger-500'
                  : 'bg-ink-800 text-ink-300'
            }`}
          >
            {ghostComparison.status === 'ahead' && `GHOST +${ghostComparison.delta}`}
            {ghostComparison.status === 'behind' && `GHOST ${ghostComparison.delta}`}
            {ghostComparison.status === 'tied' && 'GHOST TIED'}
          </div>
        )}
      </div>

      <div className="text-center text-lg font-bold uppercase tracking-wide text-volt-400">{session.prompt}</div>

      <MindGrid
        cells={session.cells}
        cellVisualState={session.cellVisualState}
        gridSize={config.gridSize}
        hideValues={hideValues}
        onSelect={select}
      />

      <div className="relative flex w-full max-w-[560px] items-center justify-between text-sm">
        <span className="font-semibold text-ink-300">
          SCORE <span className="tabular-nums text-ink-50">{session.correctCount * config.scoring.basePoints}</span>
        </span>
        <span className="font-semibold text-ink-300">
          COMBO{' '}
          <AnimatePresence mode="popLayout">
            <motion.span
              key={session.combo}
              initial={{ scale: session.combo > 0 ? 1.4 : 1, opacity: session.combo > 0 ? 0.5 : 1 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 400, damping: 15 }}
              className="inline-block tabular-nums text-thunder-400"
            >
              ×{session.combo}
            </motion.span>
          </AnimatePresence>
        </span>

        <AnimatePresence>
          {milestoneLabel && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.9 }}
              animate={{ opacity: 1, y: -28, scale: 1 }}
              exit={{ opacity: 0, y: -36 }}
              transition={{ duration: 0.25 }}
              className="pointer-events-none absolute right-0 top-0 rounded-full bg-thunder-500/15 px-3 py-1 text-xs font-bold text-thunder-400"
            >
              {milestoneLabel}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
