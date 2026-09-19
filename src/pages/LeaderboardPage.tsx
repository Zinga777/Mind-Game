import { Card } from '../components/ui/Card'

export function LeaderboardPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink-50">Leaderboard</h1>
      <Card>
        <p className="text-sm text-ink-300">
          Global, friends, and league leaderboards require a server-authoritative backend to rank real players
          fairly. This build runs in guest/local mode only, so no leaderboard is shown here rather than a fabricated
          one — see the README roadmap for the backend phase that adds this.
        </p>
      </Card>
    </div>
  )
}
