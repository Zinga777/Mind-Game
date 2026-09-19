import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card, StatTile, Badge } from '../components/ui/Card'
import { getProfile } from '../state/localProfileStore'
import type { DifficultyLevel, ObjectiveType } from '../game-engine/types'

const OBJECTIVE_CARDS: { objective: ObjectiveType; title: string; blurb: string }[] = [
  { objective: 'target-hunt', title: 'Target Hunt', blurb: 'Find each called number as fast as you can.' },
  { objective: 'ascending', title: 'Ascending', blurb: 'Clear the whole grid in rising order.' },
  { objective: 'odd-even', title: 'Odd / Even', blurb: 'Select the right parity, ascending.' },
  { objective: 'memory', title: 'Memory Grid', blurb: 'Memorize positions, then recall them.' },
]

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function HomePage() {
  const navigate = useNavigate()
  const profile = useMemo(() => getProfile(), [])
  const overallPb = Math.max(0, ...Object.values(profile.personalBests))

  const start = (objective: ObjectiveType, difficulty: DifficultyLevel = 'advanced') => {
    navigate(`/pre-game?objective=${objective}&difficulty=${difficulty}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-sm text-ink-300">{greeting()}, Athlete</div>
        <h1 className="mt-1 text-2xl font-bold text-ink-50">Your brain is an athlete.</h1>
      </div>

      <Card>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Best Score" value={overallPb.toLocaleString()} accent />
          <StatTile label="Streak" value={`${profile.streak.current}d`} />
          <StatTile label="Runs" value={profile.runs.length} />
        </div>
      </Card>

      <Button size="lg" onClick={() => start('target-hunt')} className="w-full">
        PLAY NOW
      </Button>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Mind Grid Modes</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {OBJECTIVE_CARDS.map((card) => (
            <Card
              key={card.objective}
              className="cursor-pointer transition-colors hover:border-focus-500"
              onClick={() => start(card.objective)}
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-ink-50">{card.title}</div>
                <Badge tone="focus">Grid</Badge>
              </div>
              <p className="mt-2 text-sm text-ink-300">{card.blurb}</p>
              {profile.personalBests[card.objective] != null && (
                <p className="mt-3 text-xs text-ink-400">
                  PB <span className="font-bold text-focus-400">{profile.personalBests[card.objective]}</span>
                </p>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
