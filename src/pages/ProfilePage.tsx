import { useEffect, useState } from 'react'
import { Card, StatTile, Badge } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Skeleton } from '../components/ui/Skeleton'
import { useSession } from '../state/SessionContext'
import { useToast } from '../components/ui/Toast'
import { fetchProfile, type ProfileResponse } from '../lib/profileApi'
import { ApiError } from '../lib/api'

export function ProfilePage() {
  const { user } = useSession()
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    fetchProfile()
      .then(setProfile)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (user) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink-50">{user?.displayName ?? 'Your Profile'}</h1>
        {user?.isGuest && <Badge tone="ember">Guest</Badge>}
      </div>

      {user?.isGuest && <UpgradeCard onUpgraded={load} />}

      <Card>
        {loading ? (
          <div className="grid grid-cols-3 gap-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <StatTile label="Coins" value={profile?.coins.toLocaleString() ?? '—'} accent />
            <StatTile label="Streak" value={`${profile?.streak.current ?? 0}d`} />
            <StatTile label="Longest" value={`${profile?.streak.longest ?? 0}d`} />
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Personal Bests</h2>
        {loading ? (
          <Skeleton className="h-16" />
        ) : !profile || Object.keys(profile.personalBests).length === 0 ? (
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
        {loading ? (
          <Skeleton className="h-24" />
        ) : !profile || profile.recentRuns.length === 0 ? (
          <p className="text-sm text-ink-400">No runs yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {profile.recentRuns.map((run) => (
              <div key={run.id} className="flex justify-between text-sm">
                <span className="capitalize text-ink-300">
                  {run.objective.replace('-', ' ')} · {run.difficulty}
                </span>
                <span className="tabular-nums text-ink-50">{run.finalScore.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function UpgradeCard({ onUpgraded }: { onUpgraded: () => void }) {
  const { register } = useSession()
  const { show } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register(username, password)
      show('Account created — your progress is saved.', 'success')
      onUpgraded()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create account')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="border-focus-500/30">
      <h2 className="text-sm font-semibold text-ink-50">Save your progress</h2>
      <p className="mt-1 text-xs text-ink-400">
        You're playing as a guest — this browser only. Create a username to keep your coins, streak, and bests.
      </p>
      <form onSubmit={submit} className="mt-3 flex flex-col gap-2">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-50 outline-none focus:border-focus-500"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          placeholder="Password"
          className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-50 outline-none focus:border-focus-500"
        />
        {error && <p className="text-xs text-danger-500">{error}</p>}
        <Button type="submit" disabled={submitting || !username || !password} className="mt-1">
          {submitting ? 'Creating…' : 'CREATE ACCOUNT'}
        </Button>
      </form>
    </Card>
  )
}
