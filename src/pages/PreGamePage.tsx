import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card, Badge } from '../components/ui/Card'
import { buildGameConfig, randomSeed } from '../game-engine/core/config'
import { DIFFICULTY_PRESETS } from '../game-engine/difficulty'
import { getProfile } from '../state/localProfileStore'
import type { DifficultyLevel, MutatorType, ObjectiveType } from '../game-engine/types'

const OBJECTIVE_LABEL: Record<ObjectiveType, string> = {
  ascending: 'Ascending',
  descending: 'Descending',
  'target-hunt': 'Target Hunt',
  'min-max': 'Min / Max',
  'odd-even': 'Odd / Even',
  divisibility: 'Divisibility',
  'rule-switch': 'Rule Switch',
  memory: 'Memory Grid',
}

const DIFFICULTY_ORDER: DifficultyLevel[] = ['beginner', 'intermediate', 'advanced', 'expert', 'master']
const MUTATOR_LABEL: Record<MutatorType, string> = {
  shuffle: 'Shuffle',
  vanish: 'Vanish',
  precision: 'Precision',
  turbo: 'Turbo',
  distraction: 'Distraction',
}

export function PreGamePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()

  const objective = (params.get('objective') as ObjectiveType) ?? 'target-hunt'
  const [difficulty, setDifficulty] = useState<DifficultyLevel>((params.get('difficulty') as DifficultyLevel) ?? 'advanced')
  const [countdown, setCountdown] = useState<number | null>(null)

  const preset = DIFFICULTY_PRESETS[difficulty]
  const profile = useMemo(() => getProfile(), [])
  const pb = profile.personalBests[objective]

  const config = useMemo(
    () => buildGameConfig({ objective, difficulty, mutators: preset.allowedMutators, seed: randomSeed() }),
    [objective, difficulty, preset],
  )

  useEffect(() => {
    if (countdown === null) return
    if (countdown === 0) {
      navigate('/play', { state: { config } })
      return
    }
    const timeout = setTimeout(() => setCountdown((c) => (c === null ? null : c - 1)), 700)
    return () => clearTimeout(timeout)
  }, [countdown, config, navigate])

  if (countdown !== null) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center gap-2">
        <div className="text-7xl font-black tabular-nums text-focus-400">{countdown === 0 ? 'GO' : countdown}</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Badge tone="focus">Mind Grid</Badge>
        <h1 className="mt-2 text-2xl font-bold text-ink-50">{OBJECTIVE_LABEL[objective]}</h1>
      </div>

      <Card>
        <div className="flex items-center justify-between text-sm">
          <span className="text-ink-300">Duration</span>
          <span className="font-bold text-ink-50">{preset.durationSeconds}s</span>
        </div>
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="text-ink-300">Personal Best</span>
          <span className="font-bold text-focus-400">{pb != null ? pb.toLocaleString() : '—'}</span>
        </div>
      </Card>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">Difficulty</h2>
        <div className="flex flex-wrap gap-2">
          {DIFFICULTY_ORDER.map((level) => (
            <button
              key={level}
              onClick={() => setDifficulty(level)}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
                difficulty === level
                  ? 'border-focus-500 bg-focus-500/15 text-focus-400'
                  : 'border-ink-700 bg-ink-850 text-ink-300 hover:text-ink-50'
              }`}
            >
              {DIFFICULTY_PRESETS[level].label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-400">{preset.description}</p>
      </div>

      {preset.allowedMutators.length > 0 && (
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">Modifiers</h2>
          <div className="flex flex-wrap gap-2">
            {preset.allowedMutators.map((m) => (
              <Badge key={m}>{MUTATOR_LABEL[m]}</Badge>
            ))}
          </div>
        </div>
      )}

      <Button size="lg" className="w-full" onClick={() => setCountdown(3)}>
        START
      </Button>
    </div>
  )
}
