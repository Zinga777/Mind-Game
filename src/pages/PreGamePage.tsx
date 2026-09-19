import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card, Badge } from '../components/ui/Card'
import { LightningBolt } from '../components/brand/LightningMark'
import { buildGameConfig, randomSeed } from '../game-engine/core/config'
import { DIFFICULTY_PRESETS } from '../game-engine/difficulty'
import { costForDifficulty, DEFAULT_THUNDER_CONFIG } from '../game-engine/thunder'
import { GameHistoryRepository } from '../repositories/GameHistoryRepository'
import { buildDailyConfig, ChallengeRepository } from '../repositories/ChallengeRepository'
import { useThunder } from '../state/ThunderContext'
import { playSfx } from '../services/SoundService'
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
  rotation: 'Rotation',
  mirror: 'Mirror',
  'moving-targets': 'Moving Targets',
  'locked-cells': 'Locked Cells',
  'blind-phase': 'Blind Phase',
}

export function PreGamePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { balance, spend } = useThunder()

  const isDaily = params.get('daily') === 'true'
  const quickStart = params.get('quick') === 'true'
  const objective = isDaily ? 'target-hunt' : ((params.get('objective') as ObjectiveType) ?? 'target-hunt')
  const [difficulty, setDifficulty] = useState<DifficultyLevel>(
    isDaily ? 'advanced' : ((params.get('difficulty') as DifficultyLevel) ?? 'advanced'),
  )
  const [countdown, setCountdown] = useState<number | null>(null)
  const [insufficientFunds, setInsufficientFunds] = useState(false)
  const [dailyAlreadyDone, setDailyAlreadyDone] = useState(false)

  const preset = DIFFICULTY_PRESETS[difficulty]
  const [pb, setPb] = useState<number | null>(null)

  useEffect(() => {
    GameHistoryRepository.getPersonalBest(objective).then((r) => setPb(r?.bestScore ?? null))
  }, [objective])

  useEffect(() => {
    if (!isDaily) return
    ChallengeRepository.getToday().then((d) => setDailyAlreadyDone(d.completed))
  }, [isDaily])

  const config = useMemo(() => {
    if (isDaily) return buildDailyConfig()
    return buildGameConfig({ objective, difficulty, seed: randomSeed() })
  }, [isDaily, objective, difficulty])

  const cost = isDaily ? DEFAULT_THUNDER_CONFIG.dailyChallengeCost : costForDifficulty(difficulty)
  const canAfford = balance >= cost

  useEffect(() => {
    if (countdown === null) return
    if (countdown === 0) {
      playSfx('go')
      navigate('/play', { state: { config, isDaily } })
      return
    }
    playSfx('countdown')
    const timeout = setTimeout(() => setCountdown((c) => (c === null ? null : c - 1)), 700)
    return () => clearTimeout(timeout)
  }, [countdown, config, navigate, isDaily])

  const handleStart = async () => {
    if (dailyAlreadyDone) return
    if (cost > 0) {
      const ok = await spend(cost, isDaily ? 'daily_challenge' : `game_${difficulty}`)
      if (!ok) {
        setInsufficientFunds(true)
        return
      }
    }
    setCountdown(3)
  }

  // Retry from Results skips straight back into the action — re-reading the
  // same info screen and re-tapping START is exactly the friction that kills
  // the "one more run" instinct.
  const autoStartedRef = useRef(false)
  useEffect(() => {
    if (quickStart && !autoStartedRef.current && countdown === null && !dailyAlreadyDone) {
      autoStartedRef.current = true
      handleStart()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quickStart, countdown, dailyAlreadyDone])

  if (countdown !== null) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center gap-2">
        <div className="text-7xl font-black tabular-nums text-volt-400">{countdown === 0 ? 'GO' : countdown}</div>
      </div>
    )
  }

  // While a quick-retry is auto-spending Thunder and about to launch the
  // countdown, skip the flash of the full info screen — nothing to decide.
  if (quickStart && !insufficientFunds && !dailyAlreadyDone) {
    return <div className="h-[70vh]" />
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Badge tone={isDaily ? 'thunder' : 'volt'}>{isDaily ? "Today's Mind Grid" : 'Mind Grid'}</Badge>
        <h1 className="mt-2 text-2xl font-bold text-ink-50">{OBJECTIVE_LABEL[objective]}</h1>
      </div>

      <Card>
        <div className="flex items-center justify-between text-sm">
          <span className="text-ink-300">Duration</span>
          <span className="font-bold text-ink-50">{preset.durationSeconds}s</span>
        </div>
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="text-ink-300">Personal Best</span>
          <span className="font-bold text-volt-400">{pb != null ? pb.toLocaleString() : '—'}</span>
        </div>
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="text-ink-300">Thunder Cost</span>
          <span className={`flex items-center gap-1 font-bold ${canAfford ? 'text-thunder-400' : 'text-danger-500'}`}>
            <LightningBolt className="h-3.5 w-3.5" />
            {cost === 0 ? 'Free' : cost}
          </span>
        </div>
      </Card>

      {!isDaily && (
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">Difficulty</h2>
          <div className="flex flex-wrap gap-2">
            {DIFFICULTY_ORDER.map((level) => (
              <button
                key={level}
                onClick={() => setDifficulty(level)}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
                  difficulty === level
                    ? 'border-volt-500 bg-volt-500/15 text-volt-400'
                    : 'border-ink-700 bg-ink-850 text-ink-300 hover:text-ink-50'
                }`}
              >
                {DIFFICULTY_PRESETS[level].label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-400">{preset.description}</p>
        </div>
      )}

      {config.mutators.length > 0 && (
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">Modifiers</h2>
          <div className="flex flex-wrap gap-2">
            {config.mutators.map((m) => (
              <Badge key={m}>{MUTATOR_LABEL[m]}</Badge>
            ))}
          </div>
        </div>
      )}

      {dailyAlreadyDone ? (
        <Card className="text-center text-sm text-ink-300">Today's challenge is done — come back tomorrow.</Card>
      ) : (
        <Button size="lg" className="w-full" onClick={handleStart} disabled={!canAfford}>
          {canAfford ? 'START' : 'NOT ENOUGH THUNDER'}
        </Button>
      )}

      {insufficientFunds && (
        <Card className="border-danger-500/40 text-center text-xs text-danger-500">
          Not enough Thunder for this run. Watch a rewarded ad from your Profile to recharge.
        </Card>
      )}
    </div>
  )
}
