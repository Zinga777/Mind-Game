import { useMemo } from 'react'
import { Card, StatTile } from '../components/ui/Card'
import { getProfile } from '../state/localProfileStore'

export function ProfilePage() {
  const profile = useMemo(() => getProfile(), [])

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink-50">Your Profile</h1>

      <Card>
        <div className="grid grid-cols-2 gap-3">
          <StatTile label="Current Streak" value={`${profile.streak.current}d`} />
          <StatTile label="Longest Streak" value={`${profile.streak.longest}d`} />
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Personal Bests</h2>
        {Object.keys(profile.personalBests).length === 0 ? (
          <p className="text-sm text-ink-400">Play a Mind Grid to set your first personal best.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {Object.entries(profile.personalBests).map(([objective, best]) => (
              <div key={objective} className="flex justify-between text-sm">
                <span className="capitalize text-ink-300">{objective.replace('-', ' ')}</span>
                <span className="font-bold text-focus-400">{best?.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Recent Runs</h2>
        {profile.runs.length === 0 ? (
          <p className="text-sm text-ink-400">No runs yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {profile.runs.slice(0, 8).map((run) => (
              <div key={run.id} className="flex justify-between text-sm">
                <span className="capitalize text-ink-300">{run.objective.replace('-', ' ')}</span>
                <span className="tabular-nums text-ink-50">{run.score.finalScore.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <p className="text-xs text-ink-400">
          This is guest-mode progress saved to this browser only. Creating an account (not yet implemented) would
          sync your profile, rating, and achievements to the server.
        </p>
      </Card>
    </div>
  )
}
