import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '../components/ui/Button'
import { Card, StatTile, Badge } from '../components/ui/Card'
import { LightningBolt } from '../components/brand/LightningMark'
import { usePlayer } from '../state/PlayerContext'
import { GameHistoryRepository } from '../repositories/GameHistoryRepository'
import { ChallengeRepository } from '../repositories/ChallengeRepository'
import { analyzeMindDna, type AttemptSample } from '../game-engine/performance'
import type { DailyChallengeRecord } from '../data/db'
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
  const { profile } = usePlayer()
  const [personalBests, setPersonalBests] = useState<Record<string, number>>({})
  const [streak, setStreak] = useState({ current: 0, longest: 0 })
  const [daily, setDaily] = useState<DailyChallengeRecord | null>(null)
  const [archetype, setArchetype] = useState<string | null>(null)
  const [strongest, setStrongest] = useState<string | null>(null)

  useEffect(() => {
    GameHistoryRepository.getAllPersonalBests().then((pbs) => {
      setPersonalBests(Object.fromEntries(pbs.map((p) => [p.objective, p.bestScore])))
    })
    GameHistoryRepository.getStreak().then((s) => setStreak({ current: s.current, longest: s.longest }))
    ChallengeRepository.getToday().then(setDaily)
    GameHistoryRepository.getRecent(15).then((attempts) => {
      const samples: AttemptSample[] = attempts.map((a) => ({
        objective: a.config.objective,
        difficulty: a.config.difficulty,
        mutators: a.config.mutators,
        score: a.score,
        playedAt: a.playedAt,
      }))
      const dna = analyzeMindDna(samples)
      if (dna.sampleSize > 0) {
        setArchetype(dna.archetype)
        setStrongest(dna.strongest)
      }
    })
  }, [])

  const overallPb = Math.max(0, ...Object.values(personalBests))

  const start = (objective: ObjectiveType, difficulty: DifficultyLevel = 'advanced') => {
    navigate(`/pre-game?objective=${objective}&difficulty=${difficulty}`)
  }

  // "PLAY NOW" should mean now — straight past the info screen into the countdown.
  const playNow = () => {
    navigate('/pre-game?objective=target-hunt&difficulty=advanced&quick=true')
  }

  const startDaily = () => {
    navigate('/pre-game?daily=true')
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-sm text-ink-300">
          {greeting()}, {profile?.username ?? 'Athlete'}
        </div>
        <h1 className="mt-1 text-2xl font-bold text-ink-50">Your brain is an athlete.</h1>
      </div>

      <Card>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Best Score" value={overallPb.toLocaleString()} accent />
          <StatTile label="Streak" value={`${streak.current}d`} />
          {archetype ? <StatTile label="Archetype" value={archetype} /> : <StatTile label="Runs" value={0} />}
        </div>
      </Card>

      <motion.div whileTap={{ scale: 0.98 }}>
        <Button size="lg" onClick={playNow} className="w-full">
          PLAY NOW
        </Button>
      </motion.div>

      <Card className="cursor-pointer border-thunder-500/30 transition-colors hover:border-thunder-500" onClick={startDaily}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-thunder-400">Today's Mind Grid</div>
            <div className="mt-1 text-sm text-ink-300">
              {daily?.completed ? `Completed — score ${daily.score?.toLocaleString()}` : 'Target Hunt · Advanced · Free entry'}
            </div>
          </div>
          <Badge tone={daily?.completed ? 'volt' : 'thunder'}>{daily?.completed ? 'Done' : 'Play'}</Badge>
        </div>
      </Card>

      {strongest && (
        <Card>
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-300">Strongest skill</span>
            <span className="font-bold capitalize text-volt-400">{strongest}</span>
          </div>
        </Card>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Mind Grid Modes</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {OBJECTIVE_CARDS.map((card, i) => (
            <motion.div
              key={card.objective}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card
                className="cursor-pointer transition-colors hover:border-volt-500"
                onClick={() => start(card.objective)}
              >
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-ink-50">{card.title}</div>
                  <LightningBolt className="h-4 w-4 opacity-60" />
                </div>
                <p className="mt-2 text-sm text-ink-300">{card.blurb}</p>
                {personalBests[card.objective] != null && (
                  <p className="mt-3 text-xs text-ink-400">
                    PB <span className="font-bold text-volt-400">{personalBests[card.objective]}</span>
                  </p>
                )}
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}
