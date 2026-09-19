import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Card, Badge } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { fetchLeaderboard, type LeaderboardResponse } from '../lib/profileApi'
import { DIFFICULTY_PRESETS } from '../game-engine/difficulty'
import { useSession } from '../state/SessionContext'
import type { DifficultyLevel, ObjectiveType } from '../game-engine/types'

const OBJECTIVES: { value: ObjectiveType; label: string }[] = [
  { value: 'target-hunt', label: 'Target Hunt' },
  { value: 'ascending', label: 'Ascending' },
  { value: 'odd-even', label: 'Odd / Even' },
  { value: 'memory', label: 'Memory' },
]
const DIFFICULTIES: DifficultyLevel[] = ['beginner', 'intermediate', 'advanced', 'expert', 'master']

export function LeaderboardPage() {
  const { user } = useSession()
  const [objective, setObjective] = useState<ObjectiveType>('target-hunt')
  const [difficulty, setDifficulty] = useState<DifficultyLevel>('advanced')
  const [data, setData] = useState<LeaderboardResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    let cancelled = false
    setLoading(true)
    fetchLeaderboard(objective, difficulty)
      .then((res) => !cancelled && setData(res))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [objective, difficulty, user])

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink-50">Leaderboard</h1>

      <div className="flex flex-wrap gap-2">
        {OBJECTIVES.map((o) => (
          <button
            key={o.value}
            onClick={() => setObjective(o.value)}
            className={clsx(
              'rounded-lg border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors',
              objective === o.value
                ? 'border-focus-500 bg-focus-500/15 text-focus-400'
                : 'border-ink-700 bg-ink-850 text-ink-300',
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {DIFFICULTIES.map((d) => (
          <button
            key={d}
            onClick={() => setDifficulty(d)}
            className={clsx(
              'rounded-lg border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors',
              difficulty === d ? 'border-ember-500 bg-ember-500/15 text-ember-400' : 'border-ink-700 bg-ink-850 text-ink-300',
            )}
          >
            {DIFFICULTY_PRESETS[d].label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : !data ? (
        <Card>
          <p className="text-sm text-ink-300">Couldn't reach the leaderboard right now.</p>
        </Card>
      ) : data.top.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-300">No runs yet for this mode — be the first on the board.</p>
        </Card>
      ) : (
        <Card>
          <div className="flex flex-col divide-y divide-ink-800">
            {data.top.map((row) => (
              <div
                key={row.userId}
                className={clsx(
                  'flex items-center justify-between py-2.5 text-sm',
                  row.userId === user?.id && 'font-bold text-focus-400',
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="w-8 tabular-nums text-ink-400">#{row.rank}</span>
                  <span>{row.displayName}</span>
                  {row.userId === user?.id && <Badge tone="focus">You</Badge>}
                </div>
                <span className="tabular-nums">{row.bestScore.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {data && data.myRank != null && data.myRank > data.top.length && (
        <Card className="border-focus-500/40">
          <div className="flex items-center justify-between text-sm font-bold text-focus-400">
            <span>#{data.myRank} YOU</span>
            <span className="tabular-nums">{data.myBest?.toLocaleString()}</span>
          </div>
        </Card>
      )}
    </div>
  )
}
