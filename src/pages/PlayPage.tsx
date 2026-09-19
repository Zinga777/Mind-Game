import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { MindGrid } from '../features/mind-grid/MindGrid'
import { useMindGridSession } from '../features/mind-grid/useMindGridSession'
import { computeScore } from '../game-engine/scoring'
import { isRevealPhase } from '../game-engine/objectives'
import { submitAttempt } from '../lib/profileApi'
import { enqueuePendingAttempt } from '../state/offlineQueue'
import { ApiError } from '../lib/api'
import type { GameConfig } from '../game-engine/types'

export function PlayPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const config = (location.state as { config?: GameConfig } | null)?.config

  if (!config) {
    navigate('/', { replace: true })
    return null
  }

  return <ActivePlaySession config={config} />
}

function ActivePlaySession({ config }: { config: GameConfig }) {
  const navigate = useNavigate()
  const { session, remainingMs, select } = useMindGridSession(config)
  const hasSubmitted = useRef(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (session.status !== 'completed' || hasSubmitted.current) return
    hasSubmitted.current = true
    setSubmitting(true)

    const payload = { config, events: session.events, remainingTimeMs: remainingMs, bestCombo: session.bestCombo }

    submitAttempt(payload)
      .then((result) => {
        navigate('/results', {
          state: {
            score: result.score,
            isNewPersonalBest: result.isNewPersonalBest,
            previousBest: result.previousBest,
            globalRank: result.globalRank,
            coins: result.coins,
            config,
            savedLocally: false,
          },
          replace: true,
        })
      })
      .catch((err) => {
        // Never silently lose a score: queue it for retry and show the
        // locally-computed result immediately with a "not yet confirmed" flag.
        enqueuePendingAttempt(payload)
        const localScore = computeScore(session.events, config, remainingMs, session.bestCombo)
        const isServerDown = !(err instanceof ApiError)
        navigate('/results', {
          state: {
            score: localScore,
            isNewPersonalBest: false,
            previousBest: null,
            globalRank: null,
            coins: null,
            config,
            savedLocally: true,
            submitError: isServerDown ? 'Server unreachable' : err.message,
          },
          replace: true,
        })
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.status])

  const seconds = Math.ceil(remainingMs / 1000)
  const isMemoryObjective =
    session.objective.type === 'memory' || (session.objective.type === 'rule-switch' && session.objective.sub.type === 'memory')
  const revealing = isRevealPhase(session.objective)
  const hideValues = isMemoryObjective && !revealing
  const urgentTimer = seconds <= 10

  return (
    <div className="flex flex-col items-center gap-6">
      <div className={`text-4xl font-black tabular-nums transition-colors ${urgentTimer ? 'text-danger-500' : 'text-ink-50'}`}>
        {String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')}
      </div>

      <div className="text-center text-lg font-bold uppercase tracking-wide text-focus-400">{session.prompt}</div>

      <MindGrid
        cells={session.cells}
        cellVisualState={session.cellVisualState}
        gridSize={config.gridSize}
        hideValues={hideValues}
        onSelect={select}
      />

      <div className="flex w-full max-w-[560px] items-center justify-between text-sm">
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
              className="inline-block tabular-nums text-ember-400"
            >
              ×{session.combo}
            </motion.span>
          </AnimatePresence>
        </span>
      </div>

      {submitting && <div className="text-xs text-ink-400">Submitting result…</div>}
    </div>
  )
}
