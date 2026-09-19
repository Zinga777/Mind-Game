import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { MindGrid } from '../features/mind-grid/MindGrid'
import { useMindGridSession } from '../features/mind-grid/useMindGridSession'
import { computeScore } from '../game-engine/scoring'
import { isRevealPhase } from '../game-engine/objectives'
import { recordRun } from '../state/localProfileStore'
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

  useEffect(() => {
    if (session.status !== 'completed' || hasSubmitted.current) return
    hasSubmitted.current = true

    const score = computeScore(session.events, config, remainingMs, session.bestCombo)
    const { isNewPersonalBest, previousBest } = recordRun({
      objective: config.objective,
      difficulty: config.difficulty,
      mutators: config.mutators,
      score,
      playedAtMs: Date.now(),
    })

    navigate('/results', { state: { score, isNewPersonalBest, previousBest, config }, replace: true })
  }, [session.status, session.events, session.bestCombo, remainingMs, config, navigate])

  const seconds = Math.ceil(remainingMs / 1000)
  const isMemoryObjective =
    session.objective.type === 'memory' || (session.objective.type === 'rule-switch' && session.objective.sub.type === 'memory')
  const revealing = isRevealPhase(session.objective)
  const hideValues = isMemoryObjective && !revealing

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="text-4xl font-black tabular-nums text-ink-50">
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
          COMBO <span className="tabular-nums text-ember-400">×{session.combo}</span>
        </span>
      </div>
    </div>
  )
}
